import { makeBasicSegmenter } from "./segmenters";
import type { StyledLabel, Interval, Segment, Style } from "./types";

export type LabelID = string;
type SegmentID = string;
type Index = number;

export type ManagedLabel<S extends Style, L extends StyledLabel<S>> = L & {
    id: LabelID;
}

export type ManagedSegment<S extends Style, L extends StyledLabel<S>> = Segment<S, ManagedLabel<S, L>> & {
    id: SegmentID;
}

class Lock {
    private lock = 0;

    acquire() {
        this.lock++;
    }

    release() {
        this.lock--;
    }

    isFree() {
        return this.lock <= 0;
    }
}

/**
 * Returns the subintervals of `target` that are not covered by any interval in
 * `coveredIntervals`.
 *
 * All ranges are interpreted as half-open intervals `[start, end)`. Intervals
 * that do not intersect `target` are ignored.
 */
export function getUncoveredSubintervals(
    target: Interval,
    coveredIntervals: readonly Interval[],
): Interval[] {
    if (target.start > target.end) {
        throw new Error(`Invalid target interval: [${target.start}, ${target.end})`);
    }
    if (target.start === target.end) {
        return [];
    }

    const clippedIntervals = coveredIntervals
        .map((interval) => ({
            start: Math.max(target.start, interval.start),
            end: Math.min(target.end, interval.end),
        }))
        .filter((interval) => interval.start < interval.end)
        .sort((a, b) => b.start - a.start);

    const uncovered: Interval[] = [];
    let cursor = target.end;

    for (const interval of clippedIntervals) {
        if (interval.start >= cursor) {
            continue;
        }
        if (interval.end < cursor) {
            uncovered.push({ start: interval.end, end: cursor });
        }
        cursor = interval.start;
    }

    if (target.start < cursor) {
        uncovered.push({ start: target.start, end: cursor });
    }

    return uncovered.reverse();
}

/**
 * Invariants to maintain:
 * - The segments should cover the full text without gaps or overlaps. 
 * - Each label should be fully contained within a single segment. 
 * - Each segment should have length greater than 0. 
 * - Each label should have length greater than 0.
 * - Each label's start position within the segment manager should be relative to the segment it is contained in.
 * - Essentially, the getter interface should return data consistent with the representation that LabeledText expects.
 * - The actual label data should store start pos relative to entire text.
 */
export type SegmentManager<S extends Style, L extends StyledLabel<S>> = {
    /**
     * Gets the current text.
     */
    getText(): string;
    /**
     * Gets the IDs of all segments.
     */
    getSegmentIds(): SegmentID[];
    /**
     * Gets a segment by its ID.
     */
    getSegment(id : SegmentID): Segment<S, ManagedLabel<S, L>>;
    /**
     * Gets all segments.
     */
    getSegments(): readonly ManagedSegment<S, L>[];
    /**
     * Subscribe to changes in the segments. The callback will be called whenever the segments are updated. Returns an unsubscribe function.
     * @param callback 
     */
    subscribe(callback: () => void): () => void;

    /**
     * Adds a new label. Throw an error if the label id already exists.
     */
    addLabel(id : LabelID, label: L): void;
    /**
     * Updates an existing label. If the label id does not exist, throw an error.
     * @param id 
     * @param newLabel 
     */
    updateLabel(id: LabelID, newLabel: L): void;
    /**
     * Remove a label with given id. If the label id does not exist, throw an error.
     * @param id 
     */
    removeLabel(id: LabelID): void;
    /**
     * Insert text at a given position. This may cause segments to split or merge depending on the implementation. The position is relative to the full text, not segment-local. If the position is out of bounds, throw an error.
     * @param pos 
     * @param text 
     */
    insertTextAt(pos: number, text: string): void;
    /**
     * Delete text at a given position with given length. This may cause segments to split or merge depending on the implementation. The position is relative to the full text, not segment-local. If the position is out of bounds, throw an error.
     * @param pos 
     * @param length 
     */
    deleteTextAt(pos: number, length: number): void;

    /**
     * Perform a batch of operations. 
     */
    batch(operations: (() => void)): void;
}

/**
 * Nothing here should touch the labelId - label map.
 */
type SegmentManagerInternals<S extends Style, L extends StyledLabel<S>> = {
    /**
     * Validate whether a segment can be split at the given position. The position is relative to the segment. This is used to prevent splitting in the middle of a label, for example. 
     * @param segment 
     * @param pos 
     * @returns 
     */
    validateSplit: (segment: Segment<S, ManagedLabel<S, L>>, pos : number) => boolean;
    /**
     * Query the index of the segment that contains the given index of the text. The position is relative to the full text, not segment-local. Throw an error if the position is out of bounds.
     * @param pos 
     */
    querySegment(pos: number): Index;
    /**
     * Query the first index of the segment that overlaps the given text range and the first index after that that does not overlap with the range. The positions are relative to the full text, not segment-local. Throw an error if the positions are out of bounds or if start > end.
     * @param start 
     * @param end 
     */
    querySegments(start : number, end : number) : { startIdx : Index; endIdx : Index };
    /**
     * Merge the segments between the given indices (inclusive of startIdx and exclusive of endIdx) into one segment. The new segment will span the full text range of the merged segments. Throw an error if the indices are out of bounds or if startIdx >= endIdx.
     * @param startIdx 
     * @param endIdx 
     */
    mergeSegments(startIdx: Index, endIdx: Index): SegmentID;
    /**
     * Split a segment with the given id at the given position. The position is relative to the segment. Throw an error if the position is out of bounds, if the segment id does not exist, or if the position is not a valid split point (see validateSplit).
     * @param segmentId 
     * @param relPos 
     */
    splitSegment(segmentId: SegmentID, relPos: number): void;
    /**
     * Add a segment at the end of the segments. 
     * @param segment 
     */
    postpendSegment(segment: Segment<S, ManagedLabel<S, L>>): SegmentID;

    /**
     * Add a segment at the beginning of the segments.
     * @param segment 
     */
    prependSegment(segment: Segment<S, ManagedLabel<S, L>>): SegmentID;

    /**
     * Notify all subscribers of a change. This should be called whenever the segments are updated.
     */
    notifySubscribers(): void;

    lock : Lock;

    /**
     * Generate a new segment ID. This is used internally to assign IDs to new segments. It should guarantee that the generated ID is unique among all existing segments.
     */
    idGenerator: Generator<SegmentID, never, SegmentID>;
};

type SegmentManagerData<S extends Style, L extends StyledLabel<S>> = {
    /**
     * Lookup index, not ssot
     */
    labelsById : Map<LabelID, L>;
    segmentIdsByLabelId : Map<LabelID, SegmentID>;
    segmentsById : Map<SegmentID, Segment<S, ManagedLabel<S, L>>>;
    bounds : {id : SegmentID; start : number; end : number}[]
    text : string;
    subscribers : Set<() => void>;
}

export function makeBasicSegmentManager<S extends Style, L extends StyledLabel<S>>(initialText: string, initialLabels: ManagedLabel<S, L>[], gap : number = 0): SegmentManager<S, L> {
    const segmenter = makeBasicSegmenter<S, ManagedLabel<S, L>>(gap);
    const segmentManager : SegmentManager<S, L> & SegmentManagerInternals<S, L> & SegmentManagerData<S, L> = {
        idGenerator: (function*() {
            let id = 0;
            while (true) {
                yield String(id++);
            }
        })(),
        segmentsById: new Map<SegmentID, Segment<S, ManagedLabel<S, L>>>(),
        bounds: [],
        text: "",
        labelsById: new Map<LabelID, L>(),
        segmentIdsByLabelId: new Map<LabelID, SegmentID>(),
        subscribers: new Set<() => void>(),
        lock : new Lock(),

        getText() {
            return this.text;
        },

        getSegmentIds() {
            return this.bounds.map(b => b.id);
        },

        getSegment(id: SegmentID) {
            const ret = this.segmentsById.get(id);
            if (!ret) {
                throw new Error(`Segment with ID ${id} not found`);
            }
            return ret;
        },

        getSegments() {
            return this.bounds.map(b => {
                const seg = {id : b.id, ...this.segmentsById.get(b.id)};
                return seg as ManagedSegment<S, L>;
            });
        },

        subscribe(listener : () => void) {
            this.subscribers.add(listener);
            return () => {
                this.subscribers.delete(listener);
            }
        },

        notifySubscribers() {
            if (this.lock.isFree()) {
                this.subscribers.forEach((subscriber) => subscriber());
            }
        },

        validateSplit(segment: Segment<S, ManagedLabel<S, L>>, pos: number) {
            if (pos <= 0 || pos >= segment.text.length) {
                return false;
            }
            for (const label of segment.labels) {
                if (label.interval.start < pos && label.interval.end > pos) {
                    return false;
                }
            }
            return true;
        },

        querySegment(pos: number) {
            if (pos < 0 || pos >= this.text.length) {
                throw new Error(`Position ${pos} is out of bounds for text of length ${this.text.length}`);
            }
            const idx = this.bounds.findIndex(b => b.start <= pos && b.end > pos);
            return idx;
        },

        querySegments(startPos: number, endPos: number) {
            if (startPos < 0 || endPos > this.text.length || startPos > endPos) {
                throw new Error(`Invalid segment query range: startPos=${startPos}, endPos=${endPos}, text length=${this.text.length}`);
            }
            if (startPos >= endPos) {
                throw new Error(`Invalid segment query range: startPos=${startPos} is not less than endPos=${endPos}`);
            }
            const startIdx = this.bounds.findIndex(b => b.end > startPos);
            const endIdx = this.bounds.findIndex(b => b.start >= endPos);
            if (endIdx === -1) {
                return { startIdx, endIdx: this.bounds.length };
            }
            return { startIdx, endIdx };
        },

        mergeSegments(startIdx: Index, endIdx: Index) {
            if (startIdx === -1 || endIdx === -1 || startIdx >= endIdx) {
                throw new Error(`Invalid segment indices: startIdx=${startIdx}, endIdx=${endIdx}`);
            }
            const boundsSegments = this.bounds.slice(startIdx, endIdx);
            if (boundsSegments.length === 1) {
                return boundsSegments[0].id;
            }
            const segments = boundsSegments.map(b => this.segmentsById.get(b.id) as Segment<S, ManagedLabel<S, L>>);

            let offsetTemp = 0
            let newLabels: ManagedLabel<S, L>[] = [];
            for (const seg of segments) {
                newLabels = newLabels.concat(seg.labels.map(l => ({ ...l, interval: { start: l.interval.start + offsetTemp, end: l.interval.end + offsetTemp } })));
                offsetTemp += seg.text.length;
            }
            const mergedSegment : Segment<S, ManagedLabel<S, L>> = {
                start: boundsSegments[0].start,
                text: segments.map(s => s.text).join(""),
                labels: newLabels
            }
            
            const newId = this.idGenerator.next().value;
            for (const label of mergedSegment.labels) {
                this.segmentIdsByLabelId.set(label.id, newId);
            }
            this.segmentsById.set(newId, mergedSegment);
            for (const b of boundsSegments) {
                this.segmentsById.delete(b.id);
            }
            this.bounds.splice(startIdx, endIdx - startIdx, { id: newId, start: mergedSegment.start, end: mergedSegment.start + mergedSegment.text.length });
            return newId;
        },

        splitSegment(segmentId: SegmentID, relPos: number) {
            const segment = this.segmentsById.get(segmentId);
            if (!segment) {
                throw new Error(`Segment with id ${segmentId} does not exist`);
            }
            if (!this.validateSplit(segment, relPos)) {
                throw new Error(`Position ${relPos} is not a valid split point for segment with id ${segmentId}`);
            }
            const firstHalf : Segment<S, ManagedLabel<S, L>> = {
                start: segment.start,
                text: segment.text.slice(0, relPos),
                labels: segment.labels.filter(l => l.interval.end <= relPos)
            }
            const secondId = this.idGenerator.next().value;
            const secondHalf : Segment<S, ManagedLabel<S, L>> = {
                start: segment.start + relPos,
                text: segment.text.slice(relPos),
                labels: segment.labels.filter(l => l.interval.start >= relPos).map(l => {
                    this.segmentIdsByLabelId.set(l.id, secondId);
                    return { ...l, interval: { start: l.interval.start - relPos, end: l.interval.end - relPos } }
                })
            }
            const idx = this.querySegment(segment.start);
            this.segmentsById.set(segmentId, firstHalf);
            this.segmentsById.set(secondId, secondHalf);
            this.bounds.splice(idx, 1, { id: segmentId, start: firstHalf.start, end: firstHalf.start + firstHalf.text.length }, { id: secondId, start: secondHalf.start, end: secondHalf.start + secondHalf.text.length });
        },

        postpendSegment(segment: Segment<S, ManagedLabel<S, L>>) {
            const id = this.idGenerator.next().value;
            for (const label of segment.labels) {
                this.segmentIdsByLabelId.set(label.id, id);
            }
            this.segmentsById.set(id, segment);
            this.bounds.push({ id, start: segment.start, end: segment.start + segment.text.length });
            this.text += segment.text;
            return id;
        },

        prependSegment(newSegment: Segment<S, ManagedLabel<S, L>>) {
            const id = this.idGenerator.next().value;
            for (const label of newSegment.labels) {
                this.segmentIdsByLabelId.set(label.id, id);
            }
            for (const bound of this.bounds) {
                bound.start += newSegment.text.length;
                bound.end += newSegment.text.length;
            }
            for (const [id, seg] of this.segmentsById) {
                this.segmentsById.set(id, { ...seg, start: seg.start + newSegment.text.length });
            }
            this.text = newSegment.text + this.text;
            this.segmentsById.set(id, newSegment);
            this.bounds.unshift({ id, start: newSegment.start, end: newSegment.start + newSegment.text.length });
            return id;
        },

        addLabel(id : LabelID, label: L) {
            if (this.labelsById.has(id)) {
                throw new Error(`Label with id ${id} already exists`);
            }
            const { startIdx, endIdx } = this.querySegments(label.interval.start, label.interval.end);
            const newSegmentId = this.mergeSegments(startIdx, endIdx);
            this.labelsById.set(id, label);
            this.segmentIdsByLabelId.set(id, newSegmentId);
            this.segmentsById.get(newSegmentId)!.labels.push( { ...label, interval: { start: label.interval.start - this.segmentsById.get(newSegmentId)!.start, end: label.interval.end - this.segmentsById.get(newSegmentId)!.start } , id });
            this.notifySubscribers();
        },

        removeLabel(id : LabelID) {
            const label = this.labelsById.get(id);
            if (!label) {
                throw new Error(`Label with id ${id} does not exist`);
            }
            const segmentId = this.segmentIdsByLabelId.get(id) as SegmentID;
            const segment = this.segmentsById.get(segmentId) as Segment<S, ManagedLabel<S, L>>;
            const newLabels = segment.labels.filter(l => l.id !== id);
            const newSegment : Segment<S, ManagedLabel<S, L>> = {
                start: segment.start,
                text: segment.text,
                labels: newLabels
            }
            this.segmentsById.set(segmentId, newSegment);
            this.labelsById.delete(id);
            this.segmentIdsByLabelId.delete(id);
            // Try to split the segment
            const uncovered = getUncoveredSubintervals({ start: label.interval.start, end: label.interval.end }, newLabels.map(l => l.interval));
            if (uncovered.length === 0) {
                this.notifySubscribers();
                return;
            }
            for (const range of uncovered) {
                if (range.end - range.start < gap) {
                    continue;
                }
                const splitPos = range.start - segment.start;
                this.splitSegment(segmentId, splitPos);
            }
            this.notifySubscribers();
        },

        updateLabel(id: LabelID, newLabel: L) {
            this.batch(() => {
                this.removeLabel(id);
                this.addLabel(id, newLabel);
            });
        },

        insertTextAt(pos : number, text : string) {
            if (text.length === 0) {
                return;
            }
            if (pos === 0) {
                this.prependSegment({ start: 0, text, labels: [] });
                this.notifySubscribers();
                return;
            }
            if (pos === this.text.length) {
                this.postpendSegment({ start: pos, text, labels: [] });
                this.notifySubscribers();
                return;
            }
            if (pos < 0 || pos > this.text.length) {
                throw new Error(`Position ${pos} is out of bounds for text of length ${this.text.length}`);
            }
            const idx = this.querySegment(pos);
            const segmentId = this.bounds[idx].id;
            const segment = this.segmentsById.get(segmentId) as Segment<S, ManagedLabel<S, L>>;
            const relPos = pos - segment.start;
            const overlappingLabels = segment.labels.filter(l => l.interval.start < relPos && l.interval.end > relPos);
            const idsToRemove = overlappingLabels.map(l => l.id);
            segment.labels = segment.labels.filter(l => !idsToRemove.includes(l.id));
            for (const label of overlappingLabels) {
                this.labelsById.delete(label.id);
                this.segmentIdsByLabelId.delete(label.id);
            }
            const gapRange = { start : segment.labels.filter(l => l.interval.end <= relPos).reduce((max, l) => Math.max(max, l.interval.end), 0), end: segment.labels.filter(l => l.interval.start >= relPos).reduce((min, l) => Math.min(min, l.interval.start), segment.text.length) };
            if (gapRange.end - gapRange.start < gap) {
                const labelsAfter = segment.labels.filter(l => l.interval.start >= relPos);
                for (const label of labelsAfter) {
                    label.interval.start += text.length;
                    label.interval.end += text.length;
                    this.labelsById.get(label.id)!.interval.start += text.length;
                    this.labelsById.get(label.id)!.interval.end += text.length;
                }
                segment.text = segment.text.slice(0, relPos) + text + segment.text.slice(relPos);
                this.text = this.text.slice(0, pos) + text + this.text.slice(pos);
                this.segmentsById.set(segmentId, segment);
                this.bounds[idx].end += text.length;
                this.bounds.slice(idx + 1).forEach(b => { b.start += text.length; b.end += text.length; this.segmentsById.get(b.id)!.start += text.length });
            }
            else {
                let startOff = 0;
                if (gapRange.end < segment.text.length) {
                    this.splitSegment(segmentId, gapRange.end);
                }
                if (gapRange.start > 0) {
                    this.splitSegment(segmentId, gapRange.start);
                    startOff = 1;
                }
                const gapSegment = this.segmentsById.get(this.bounds[idx + startOff].id);
                const gapRelPos = relPos - gapRange.start;
                gapSegment!.text = gapSegment!.text.slice(0, gapRelPos) + text + gapSegment!.text.slice(gapRelPos);
                this.text = this.text.slice(0, pos) + text + this.text.slice(pos);
                this.segmentsById.set(this.bounds[idx + startOff].id, gapSegment!);
                this.bounds[idx + startOff].end += text.length;
                this.bounds.slice(idx + startOff + 1).forEach(b => { b.start += text.length; b.end += text.length; this.segmentsById.get(b.id)!.start += text.length });
            }
            this.notifySubscribers();
        },
        
        deleteTextAt(pos: number, length: number) {
            if (length < 0) {
                throw new Error(`Delete length must be non-negative, got ${length}`);
            }
            if (length === 0) {
                return;
            }
            if (pos < 0 || pos + length > this.text.length) {
                throw new Error(`Delete range [${pos}, ${pos + length}) is out of bounds for text of length ${this.text.length}`);
            }

            const endPos = pos + length;
            const { startIdx, endIdx } = this.querySegments(pos, endPos);
            const affectedBounds = this.bounds.slice(startIdx, endIdx);
            if (affectedBounds.length === 0) {
                this.text = this.text.slice(0, pos) + this.text.slice(endPos);
                this.notifySubscribers();
                return;
            }

            const affectedStart = affectedBounds[0].start;
            const affectedEnd = affectedBounds[affectedBounds.length - 1].end;
            const affectedSegments = affectedBounds.map((bound) => this.segmentsById.get(bound.id)!);

            const deletedLabelIds = new Set<LabelID>();
            for (const segment of affectedSegments) {
                for (const label of segment.labels) {
                    const labelStart = segment.start + label.interval.start;
                    const labelEnd = segment.start + label.interval.end;
                    if (labelStart < endPos && labelEnd > pos) {
                        deletedLabelIds.add(label.id);
                    }
                }
            }

            for (const labelId of deletedLabelIds) {
                this.labelsById.delete(labelId);
                this.segmentIdsByLabelId.delete(labelId);
            }

            this.text = this.text.slice(0, pos) + this.text.slice(endPos);

            for (const [, label] of this.labelsById) {
                if (label.interval.start >= endPos) {
                    label.interval.start -= length;
                    label.interval.end -= length;
                }
            }

            for (const bound of affectedBounds) {
                this.segmentsById.delete(bound.id);
            }
            this.bounds.splice(startIdx, endIdx - startIdx);

            for (const bound of this.bounds.slice(startIdx)) {
                bound.start -= length;
                bound.end -= length;
                this.segmentsById.get(bound.id)!.start -= length;
            }

            const rebuiltText = this.text.slice(affectedStart, affectedEnd - length);
            const affectedSegmentIds = new Set(affectedBounds.map((bound) => bound.id));
            const rebuiltLabels = Array.from(this.labelsById.entries())
                .filter(([labelId]) => affectedSegmentIds.has(this.segmentIdsByLabelId.get(labelId)!))
                .map(([labelId, label]) => ({ ...label, id: labelId }));

            const localRebuiltLabels = rebuiltLabels.map((label) => ({
                ...label,
                interval: {
                    start: label.interval.start - affectedStart,
                    end: label.interval.end - affectedStart,
                },
            }));
            const rebuiltSegments = segmenter(rebuiltText, localRebuiltLabels).map((segment) => ({
                ...segment,
                start: segment.start + affectedStart,
            }));

            const rebuiltBounds: { id: SegmentID; start: number; end: number }[] = [];
            for (const segment of rebuiltSegments) {
                const id = this.idGenerator.next().value;
                for (const label of segment.labels) {
                    this.segmentIdsByLabelId.set(label.id, id);
                }
                this.segmentsById.set(id, segment);
                rebuiltBounds.push({ id, start: segment.start, end: segment.start + segment.text.length });
            }
            this.bounds.splice(startIdx, 0, ...rebuiltBounds);
            this.notifySubscribers();
        },

        batch(operations: () => void) {
            this.lock.acquire();
            try {
                operations();
            }
            finally {
                this.lock.release();
                this.notifySubscribers();
            }
        }
    }
    for (const label of initialLabels) {
        segmentManager.labelsById.set(label.id, label);
    }
    const segments = segmenter(initialText, initialLabels);
    for (const segment of segments) {
        segmentManager.postpendSegment(segment);
    }
    return segmentManager as SegmentManager<S, L>;
}
