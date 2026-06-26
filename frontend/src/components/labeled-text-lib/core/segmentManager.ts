import { createLogger } from "@/lib/logging";
import { makeBasicSegmenter } from "./segmenters";
import type { StyledLabel, Interval, Segment, Style } from "./types";
import { Brand } from "effect";

const logger = createLogger("SegmentManager");

type SegmentID = string & Brand.Brand<"SegmentID">;
const SegmentID = Brand.nominal<SegmentID>();
type Index = number;

export type ManagedLabel<S extends Style, L extends StyledLabel<S>, ID extends string> = L & {
	id: ID;
};

export type ManagedSegment<S extends Style, L extends StyledLabel<S>, ID extends string> = Segment<
	S,
	ManagedLabel<S, L, ID>
> & {
	id: SegmentID;
};

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
		logger.error(
			`Invalid target interval with start greater than end: [${target.start}, ${target.end})`,
		);
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
 * We say a position is relative to a segment if it is an offset from the start of the segment. We say a position is absolute if it is an offset from the start of the full text.
 *
 * Invariants to maintain:
 * - The segments should cover the full text without gaps or overlaps.
 * - Each label should be fully contained within a single segment.
 * - Each segment should have length greater than 0.
 * - Each label should have length greater than 0.
 * - Each label's start position within the segment manager should be relative to the segment it is contained in.
 * - The segment interfaces should return data consistent with the representation that LabeledText expects (e.g. labels have relative positions, segment has absolute position).
 * - The actual label data should be exposed in absolute positions. Internal stores should be relative.
 */
export type SegmentManager<S extends Style, L extends StyledLabel<S>, ID extends string> = {
	/**
	 * Gets the current text.
	 */
	getText(): string;
	/**
	 * Gets the IDs of all segments.
	 */
	getSegmentIds(): SegmentID[];
	/**
	 * Gets a segment by its ID. The segment contains labels with relative positions but the segment's position is absolute.
	 * @param id
	 */
	getSegment(id: SegmentID): Segment<S, ManagedLabel<S, L, ID>>;
	/**
	 * Gets all segments.
	 */
	getSegments(): readonly ManagedSegment<S, L, ID>[];
	/**
	 * Subscribe to changes in the segments. The callback will be called whenever the segments are updated. Returns an unsubscribe function.
	 * @param callback
	 */
	subscribe(callback: () => void): () => void;

	/**
	 * Adds a new label. The label's position should be absolute. Throw an error if the label id already exists.
	 */
	addLabel(id: ID, label: L): void;
	/**
	 * Updates an existing label. The new label's position should be absolute. If the label id does not exist, throw an error.
	 * @param id
	 * @param newLabel
	 */
	updateLabel(id: ID, newLabel: L): void;
	/**
	 * Remove a label with given id. If the label id does not exist, throw an error.
	 * @param id
	 */
	removeLabel(id: ID): void;

	/**
	 * Gets a label by its ID. Returns the label with absolute positions. Throw an error if the label id does not exist.
	 */
	getLabel(id: ID): L;
	/**
	 * Returns the IDs of all labels that cover the given absolute position.
	 * @param pos
	 */
	labelsAt(pos: number): ID[];
	/**
	 * Insert text at a given position. This may cause segments to split or merge depending on the implementation. The position is absolute. If the position is out of bounds, throw an error.
	 * @param pos
	 * @param text
	 */
	insertTextAt(pos: number, text: string): void;
	/**
	 * Delete text at a given position with given length. This may cause segments to split or merge depending on the implementation. The position is absolute. If the position is out of bounds, throw an error.
	 * @param pos
	 * @param length
	 */
	deleteTextAt(pos: number, length: number): void;

	/**
	 * Perform a batch of operations (i.e. delay notification to subscribers until the end of the batch). Can nest batch operations.
	 */
	batch(operations: () => void): void;
};

/**
 * Nothing here should touch the labelId - label map.
 */
type SegmentManagerInternals<S extends Style, L extends StyledLabel<S>, ID extends string> = {
	/**
	 * Validate whether a segment can be split at the given position. The position is relative to the segment. This is used to prevent splitting in the middle of a label, for example.
	 * @param segment
	 * @param pos
	 * @returns
	 */
	validateSplit: (segment: Segment<S, ManagedLabel<S, L, ID>>, pos: number) => boolean;
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
	querySegments(start: number, end: number): { startIdx: Index; endIdx: Index };
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
	postpendSegment(segment: Segment<S, ManagedLabel<S, L, ID>>): SegmentID;

	/**
	 * Add a segment at the beginning of the segments.
	 * @param segment
	 */
	prependSegment(segment: Segment<S, ManagedLabel<S, L, ID>>): SegmentID;

	/**
	 * Notify all subscribers of a change. This should be called whenever the segments are updated.
	 */
	notifySubscribers(): void;

	lock: Lock;

	/**
	 * Generate a new segment ID. This is used internally to assign IDs to new segments. It should guarantee that the generated ID is unique among all existing segments.
	 */
	idGenerator: Generator<SegmentID, never, SegmentID>;
};

type SegmentManagerData<S extends Style, L extends StyledLabel<S>, ID extends string> = {
	/**
	 * Lookup index, not ssot
	 */
	labelsById: Map<ID, L>; // L stored with relative pos, translation layer at interface boundary
	segmentIdsByLabelId: Map<ID, SegmentID>;
	segmentsById: Map<SegmentID, Segment<S, ManagedLabel<S, L, ID>>>;
	bounds: { id: SegmentID; start: number; end: number }[];
	text: string;
	subscribers: Set<() => void>;
};

export function makeBasicSegmentManager<
	S extends Style,
	L extends StyledLabel<S>,
	ID extends string,
>(
	initialText: string,
	initialLabels: ManagedLabel<S, L, ID>[],
	gap: number = 0,
): SegmentManager<S, L, ID> {
	const segmenter = makeBasicSegmenter<S, ManagedLabel<S, L, ID>>(gap);
	const segmentManager: SegmentManager<S, L, ID> &
		SegmentManagerInternals<S, L, ID> &
		SegmentManagerData<S, L, ID> = {
		idGenerator: (function* () {
			let id = 0;
			while (true) {
				yield SegmentID(`${id++}`);
			}
		})(),
		segmentsById: new Map<SegmentID, Segment<S, ManagedLabel<S, L, ID>>>(),
		bounds: [],
		text: "",
		labelsById: new Map<ID, L>(),
		segmentIdsByLabelId: new Map<ID, SegmentID>(),
		subscribers: new Set<() => void>(),
		lock: new Lock(),

		getText() {
			return this.text;
		},

		getSegmentIds() {
			return this.bounds.map((b) => b.id);
		},

		getSegment(id: SegmentID) {
			const ret = this.segmentsById.get(id);
			if (!ret) {
				throw new Error(`Segment with ID ${id} not found`);
			}
			return ret;
		},

		getSegments() {
			return this.bounds.map((b) => {
				const seg = { id: b.id, ...this.segmentsById.get(b.id) };
				return seg as ManagedSegment<S, L, ID>;
			});
		},

		getLabel(id: ID) {
			const label = this.labelsById.get(id);
			if (!label) {
				logger.error(`Label with ID ${id} not found`);
				throw new Error(`Label with ID ${id} not found`);
			}
			const segmentId = this.segmentIdsByLabelId.get(id);
			if (!segmentId) {
				logger.error(`Segment for label ID ${id} not found`);
				throw new Error(`Segment for label ID ${id} not found`);
			}
			const segment = this.segmentsById.get(segmentId);
			if (!segment) {
				logger.error(`Segment with ID ${segmentId} not found`);
				throw new Error(`Segment with ID ${segmentId} not found`);
			}
			return {
				...label,
				interval: {
					start: label.interval.start + segment.start,
					end: label.interval.end + segment.start,
				},
			};
		},

		labelsAt(pos: number) {
			const idx = this.querySegment(pos);
			const bound = this.bounds[idx];
			const seg = this.segmentsById.get(bound.id)!;
			const relPos = pos - bound.start;
			return seg.labels
				.filter((l) => l.interval.start <= relPos && relPos < l.interval.end)
				.map((l) => l.id);
		},

		subscribe(listener: () => void) {
			this.subscribers.add(listener);
			return () => {
				this.subscribers.delete(listener);
			};
		},

		notifySubscribers() {
			if (this.lock.isFree()) {
				this.subscribers.forEach((subscriber) => subscriber());
			}
		},

		validateSplit(segment: Segment<S, ManagedLabel<S, L, ID>>, pos: number) {
			if (pos < 0 || pos > segment.text.length) {
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
				logger.error(
					`Position ${pos} is out of bounds for text of length ${this.text.length}`,
				);
				throw new Error(
					`Position ${pos} is out of bounds for text of length ${this.text.length}`,
				);
			}
			const idx = this.bounds.findIndex((b) => b.start <= pos && b.end > pos);
			return idx;
		},

		querySegments(startPos: number, endPos: number) {
			if (startPos < 0 || endPos > this.text.length || startPos > endPos) {
				logger.error(
					`Invalid segment query range: startPos=${startPos}, endPos=${endPos}, text length=${this.text.length}`,
				);
				throw new Error(
					`Invalid segment query range: startPos=${startPos}, endPos=${endPos}, text length=${this.text.length}`,
				);
			}
			if (startPos >= endPos) {
				logger.error(
					`Invalid segment query range: startPos=${startPos} is not less than endPos=${endPos}`,
				);
				throw new Error(
					`Invalid segment query range: startPos=${startPos} is not less than endPos=${endPos}`,
				);
			}
			const startIdx = this.bounds.findIndex((b) => b.end > startPos);
			const endIdx = this.bounds.findIndex((b) => b.start >= endPos);
			if (endIdx === -1) {
				return { startIdx, endIdx: this.bounds.length };
			}
			return { startIdx, endIdx };
		},

		mergeSegments(startIdx: Index, endIdx: Index) {
			if (startIdx === -1 || endIdx === -1 || startIdx >= endIdx) {
				logger.error(
					`Invalid segment indices for merging: startIdx=${startIdx}, endIdx=${endIdx}`,
				);
				throw new Error(`Invalid segment indices: startIdx=${startIdx}, endIdx=${endIdx}`);
			}
			const boundsSegments = this.bounds.slice(startIdx, endIdx);
			if (boundsSegments.length === 1) {
				return boundsSegments[0].id;
			}
			const segments = boundsSegments.map(
				(b) => this.segmentsById.get(b.id) as Segment<S, ManagedLabel<S, L, ID>>,
			);

			let offsetTemp = 0;
			let newLabels: ManagedLabel<S, L, ID>[] = [];
			for (const seg of segments) {
				newLabels = newLabels.concat(
					seg.labels.map((l) => {
						const interval = {
							start: l.interval.start + offsetTemp,
							end: l.interval.end + offsetTemp,
						};
						this.labelsById.get(l.id)!.interval = interval;
						return { ...l, interval };
					}),
				);
				offsetTemp += seg.text.length;
			}
			const mergedSegment: Segment<S, ManagedLabel<S, L, ID>> = {
				start: boundsSegments[0].start,
				text: segments.map((s) => s.text).join(""),
				labels: newLabels,
			};

			const newId = this.idGenerator.next().value;
			for (const label of mergedSegment.labels) {
				this.segmentIdsByLabelId.set(label.id, newId);
			}
			this.segmentsById.set(newId, mergedSegment);
			for (const b of boundsSegments) {
				this.segmentsById.delete(b.id);
			}
			this.bounds.splice(startIdx, endIdx - startIdx, {
				id: newId,
				start: mergedSegment.start,
				end: mergedSegment.start + mergedSegment.text.length,
			});
			return newId;
		},

		splitSegment(segmentId: SegmentID, relPos: number) {
			const segment = this.segmentsById.get(segmentId);
			if (!segment) {
				logger.error(`Segment with id ${segmentId} does not exist`);
				throw new Error(`Segment with id ${segmentId} does not exist`);
			}
			if (relPos === 0 || relPos === segment.text.length) {
				logger.info(
					`Split position ${relPos} is at the boundary of the segment, no split needed`,
				);
				return;
			}
			if (!this.validateSplit(segment, relPos)) {
				logger.error(
					`Position ${relPos} is not a valid split point for segment with id ${segmentId}`,
				);
				throw new Error(
					`Position ${relPos} is not a valid split point for segment with id ${segmentId}`,
				);
			}
			const firstHalf: Segment<S, ManagedLabel<S, L, ID>> = {
				start: segment.start,
				text: segment.text.slice(0, relPos),
				labels: segment.labels.filter((l) => l.interval.end <= relPos),
			};
			const secondId = this.idGenerator.next().value;
			const secondHalf: Segment<S, ManagedLabel<S, L, ID>> = {
				start: segment.start + relPos,
				text: segment.text.slice(relPos),
				labels: segment.labels
					.filter((l) => l.interval.start >= relPos)
					.map((l) => {
						const interval = {
							start: l.interval.start - relPos,
							end: l.interval.end - relPos,
						};
						this.segmentIdsByLabelId.set(l.id, secondId);
						this.labelsById.get(l.id)!.interval = interval;
						return { ...l, interval };
					}),
			};
			const idx = this.querySegment(segment.start);
			this.segmentsById.set(segmentId, firstHalf);
			this.segmentsById.set(secondId, secondHalf);
			this.bounds.splice(
				idx,
				1,
				{
					id: segmentId,
					start: firstHalf.start,
					end: firstHalf.start + firstHalf.text.length,
				},
				{
					id: secondId,
					start: secondHalf.start,
					end: secondHalf.start + secondHalf.text.length,
				},
			);
		},

		postpendSegment(segment: Segment<S, ManagedLabel<S, L, ID>>) {
			const id = this.idGenerator.next().value;
			for (const label of segment.labels) {
				this.segmentIdsByLabelId.set(label.id, id);
			}
			this.segmentsById.set(id, segment);
			this.bounds.push({
				id,
				start: segment.start,
				end: segment.start + segment.text.length,
			});
			this.text += segment.text;
			return id;
		},

		prependSegment(newSegment: Segment<S, ManagedLabel<S, L, ID>>) {
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
			this.bounds.unshift({
				id,
				start: newSegment.start,
				end: newSegment.start + newSegment.text.length,
			});
			return id;
		},

		addLabel(id: ID, label: L) {
			if (this.labelsById.has(id)) {
				logger.error(`Label with id ${id} already exists`);
				throw new Error(`Label with id ${id} already exists`);
			}
			const { startIdx, endIdx } = this.querySegments(
				label.interval.start,
				label.interval.end,
			);
			const newSegmentId = this.mergeSegments(startIdx, endIdx);
			const newSegment = this.getSegment(newSegmentId);
			this.labelsById.set(id, {
				...label,
				interval: {
					start: label.interval.start - newSegment.start,
					end: label.interval.end - newSegment.start,
				},
			});
			this.segmentIdsByLabelId.set(id, newSegmentId);
			this.segmentsById.get(newSegmentId)!.labels.push({
				...label,
				interval: {
					start: label.interval.start - this.segmentsById.get(newSegmentId)!.start,
					end: label.interval.end - this.segmentsById.get(newSegmentId)!.start,
				},
				id,
			});
			this.notifySubscribers();
		},

		removeLabel(id: ID) {
			const label = this.labelsById.get(id);
			if (!label) {
				logger.error(`Label with id ${id} does not exist`);
				throw new Error(`Label with id ${id} does not exist`);
			}
			const segmentId = this.segmentIdsByLabelId.get(id) as SegmentID;
			const segment = this.segmentsById.get(segmentId) as Segment<S, ManagedLabel<S, L, ID>>;
			const newLabels = segment.labels.filter((l) => l.id !== id);
			const newSegment: Segment<S, ManagedLabel<S, L, ID>> = {
				start: segment.start,
				text: segment.text,
				labels: newLabels,
			};
			this.segmentsById.set(segmentId, newSegment);
			this.labelsById.delete(id);
			this.segmentIdsByLabelId.delete(id);
			// Try to split the segment
			const uncovered = getUncoveredSubintervals(
				{ start: label.interval.start, end: label.interval.end },
				newLabels.map((l) => l.interval),
			);
			if (uncovered.length === 0) {
				this.notifySubscribers();
				return;
			}
			for (const range of uncovered) {
				if (range.end - range.start < gap) {
					continue;
				}
				const splitPos = range.start;
				this.splitSegment(segmentId, splitPos);
			}
			this.notifySubscribers();
		},

		updateLabel(id: ID, newLabel: L) {
			this.batch(() => {
				this.removeLabel(id);
				this.addLabel(id, newLabel);
			});
		},

		insertTextAt(pos: number, text: string) {
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
				logger.error(
					`Position ${pos} is out of bounds for text of length ${this.text.length}`,
				);
				throw new Error(
					`Position ${pos} is out of bounds for text of length ${this.text.length}`,
				);
			}
			const idx = this.querySegment(pos);
			const segmentId = this.bounds[idx].id;
			const segment = this.segmentsById.get(segmentId) as Segment<S, ManagedLabel<S, L, ID>>;
			const relPos = pos - segment.start;
			const overlappingLabels = segment.labels.filter(
				(l) => l.interval.start < relPos && l.interval.end > relPos,
			);
			const idsToRemove = overlappingLabels.map((l) => l.id);
			segment.labels = segment.labels.filter((l) => !idsToRemove.includes(l.id));
			for (const label of overlappingLabels) {
				this.labelsById.delete(label.id);
				this.segmentIdsByLabelId.delete(label.id);
			}
			const gapRange = {
				start: segment.labels
					.filter((l) => l.interval.end <= relPos)
					.reduce((max, l) => Math.max(max, l.interval.end), 0),
				end: segment.labels
					.filter((l) => l.interval.start >= relPos)
					.reduce((min, l) => Math.min(min, l.interval.start), segment.text.length),
			};
			if (gapRange.end - gapRange.start < gap) {
				const labelsAfter = segment.labels.filter((l) => l.interval.start >= relPos);
				for (const label of labelsAfter) {
					const interval = {
						start: label.interval.start + text.length,
						end: label.interval.end + text.length,
					};
					label.interval = interval;
					this.labelsById.get(label.id)!.interval = interval;
				}
				segment.text = segment.text.slice(0, relPos) + text + segment.text.slice(relPos);
				this.text = this.text.slice(0, pos) + text + this.text.slice(pos);
				this.segmentsById.set(segmentId, segment);
				this.bounds[idx].end += text.length;
				this.bounds.slice(idx + 1).forEach((b) => {
					b.start += text.length;
					b.end += text.length;
					this.segmentsById.get(b.id)!.start += text.length;
				});
			} else {
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
				gapSegment!.text =
					gapSegment!.text.slice(0, gapRelPos) + text + gapSegment!.text.slice(gapRelPos);
				this.text = this.text.slice(0, pos) + text + this.text.slice(pos);
				this.segmentsById.set(this.bounds[idx + startOff].id, gapSegment!);
				this.bounds[idx + startOff].end += text.length;
				this.bounds.slice(idx + startOff + 1).forEach((b) => {
					b.start += text.length;
					b.end += text.length;
					this.segmentsById.get(b.id)!.start += text.length;
				});
			}
			this.notifySubscribers();
		},

		deleteTextAt(startPos: number, length: number) {
			// this function has lots of edge cases
			// todo: refactor into smaller functions and add more comments
			if (length < 0) {
				logger.error(`Delete length must be non-negative, got ${length}`);
				throw new Error(`Delete length must be non-negative, got ${length}`);
			}
			if (length === 0) {
				return;
			}
			if (startPos < 0 || startPos + length > this.text.length) {
				logger.error(
					`Delete range [${startPos}, ${startPos + length}) is out of bounds for text of length ${this.text.length}`,
				);
				throw new Error(
					`Delete range [${startPos}, ${startPos + length}) is out of bounds for text of length ${this.text.length}`,
				);
			}

			const endPos = startPos + length;
			const { startIdx, endIdx } = this.querySegments(startPos, endPos);
			const affectedBounds = this.bounds.slice(startIdx, endIdx);
			this.text = this.text.slice(0, startPos) + this.text.slice(endPos);
			if (affectedBounds.length === 0) {
				//pass
			}
			// only one segment affected, edge case
			//      [____dddddd_____]
			//    l1:  1111
			//    l2:        2222
			//    l3: 33
			//    l4:             44
			else if (
				affectedBounds.length === 1 &&
				affectedBounds[0].start === startPos &&
				affectedBounds[0].end === endPos
			) {
				// the deleted part is exactly the whole segment, just delete it and update bounds
				const segment = this.segmentsById.get(affectedBounds[0].id)!;
				segment.labels.forEach((l) => {
					this.labelsById.delete(l.id);
					this.segmentIdsByLabelId.delete(l.id);
				});
				this.segmentsById.delete(affectedBounds[0].id);
				this.bounds.splice(startIdx, 1);
				this.bounds.slice(startIdx).forEach((b) => {
					b.start -= length;
					b.end -= length;
					this.segmentsById.get(b.id)!.start -= length;
				});
			} else if (affectedBounds.length === 1) {
				const segment = this.segmentsById.get(affectedBounds[0].id)!;
				const relStart = startPos - segment.start;
				const relEnd = endPos - segment.start;
				// first pass, don't update ranges
				// e.g. delete labels of type 1 and 2
				const newLabelsLeft = segment.labels.filter((l) => l.interval.end <= relStart);
				const newLabelsRight = segment.labels.filter((l) => l.interval.start >= relEnd);
				const deletedLabels = segment.labels.filter(
					(l) => !(l.interval.end <= relStart || l.interval.start >= relEnd),
				);
				for (const label of deletedLabels) {
					this.labelsById.delete(label.id);
					this.segmentIdsByLabelId.delete(label.id);
				}
				segment.labels = [...newLabelsLeft, ...newLabelsRight];
				const leftUp = Math.max(0, ...newLabelsLeft.map((l) => l.interval.end));
				const rightDown = Math.min(
					segment.text.length,
					...newLabelsRight.map((l) => l.interval.start),
				);
				if (relStart - leftUp + (rightDown - relEnd) < gap) {
					// can't split, just delete and update labels of type 4 / modify bounds
					for (const label of newLabelsRight) {
						const interval = {
							start: label.interval.start - length,
							end: label.interval.end - length,
						};
						label.interval = interval;
						this.labelsById.get(label.id)!.interval = interval;
					}
					segment.text = segment.text.slice(0, relStart) + segment.text.slice(relEnd);
					this.bounds[startIdx].end -= length;
					this.bounds.slice(startIdx + 1).forEach((b) => {
						b.start -= length;
						b.end -= length;
						this.segmentsById.get(b.id)!.start -= length;
					});
				} else {
					if (leftUp === 0 && rightDown === segment.text.length) {
						// all labels are deleted, just update the segment text and bounds
						segment.text = segment.text.slice(0, relStart) + segment.text.slice(relEnd);
						this.bounds[startIdx].end -= length;
						this.bounds.slice(startIdx + 1).forEach((b) => {
							b.start -= length;
							b.end -= length;
							this.segmentsById.get(b.id)!.start -= length;
						});
					} else if (rightDown === segment.text.length) {
						// no labels of type 4
						this.splitSegment(affectedBounds[0].id, leftUp);
						const newSegment = this.segmentsById.get(this.bounds[startIdx + 1].id)!;
						newSegment.text =
							newSegment.text.slice(0, relStart - leftUp) +
							newSegment.text.slice(relEnd - leftUp);
						this.bounds[startIdx + 1].end -= length;
						this.bounds.slice(startIdx + 2).forEach((b) => {
							b.start -= length;
							b.end -= length;
							this.segmentsById.get(b.id)!.start -= length;
						});
						if (this.bounds[startIdx + 1].end === this.bounds[startIdx + 1].start) {
							this.segmentsById.delete(this.bounds[startIdx + 1].id);
							this.bounds.splice(startIdx + 1, 1);
						}
					} else if (leftUp === 0) {
						// no labels of type 3
						this.splitSegment(affectedBounds[0].id, rightDown);
						const newSegment = this.segmentsById.get(this.bounds[startIdx].id)!;
						newSegment.text =
							newSegment.text.slice(0, relStart) + newSegment.text.slice(relEnd);
						this.bounds[startIdx].end -= length;
						this.bounds.slice(startIdx + 1).forEach((b) => {
							b.start -= length;
							b.end -= length;
							this.segmentsById.get(b.id)!.start -= length;
						});
						if (this.bounds[startIdx].end === this.bounds[startIdx].start) {
							this.segmentsById.delete(this.bounds[startIdx].id);
							this.bounds.splice(startIdx, 1);
						}
					} else {
						// split twice and modify the middle segment
						this.splitSegment(affectedBounds[0].id, leftUp);
						this.splitSegment(this.bounds[startIdx + 1].id, rightDown - leftUp);
						const newSegment = this.segmentsById.get(this.bounds[startIdx + 1].id)!;
						if (newSegment.text.length === length) {
							// the deleted part is exactly the middle segment, just delete it and update bounds
							this.segmentsById.delete(this.bounds[startIdx + 1].id);
							this.bounds.splice(startIdx + 1, 1);
							this.bounds.slice(startIdx + 1).forEach((b) => {
								b.start -= length;
								b.end -= length;
								this.segmentsById.get(b.id)!.start -= length;
							});
						} else {
							newSegment.text =
								newSegment.text.slice(0, relStart - leftUp) +
								newSegment.text.slice(relEnd - leftUp);
							this.bounds[startIdx + 1].end -= length;
							this.bounds.slice(startIdx + 2).forEach((b) => {
								b.start -= length;
								b.end -= length;
								this.segmentsById.get(b.id)!.start -= length;
							});
						}
					}
				}
			} else {
				// we modify two different segments and delete all segments in between
				affectedBounds.slice(1, -1).forEach((b) => {
					const segment = this.segmentsById.get(b.id);
					segment!.labels.forEach((l) => {
						this.labelsById.delete(l.id);
						this.segmentIdsByLabelId.delete(l.id);
					});
					this.segmentsById.delete(b.id);
				});
				const firstSegment = this.segmentsById.get(affectedBounds[0].id)!;
				let firstDeleted = false;
				const lastSegment = this.segmentsById.get(
					affectedBounds[affectedBounds.length - 1].id,
				)!;
				let lastDeleted = false;
				if (startPos - firstSegment.start === 0) {
					firstSegment.labels.forEach((l) => {
						this.labelsById.delete(l.id);
						this.segmentIdsByLabelId.delete(l.id);
					});
					this.segmentsById.delete(affectedBounds[0].id);
					firstDeleted = true;
				} else {
					firstSegment.text = firstSegment.text.slice(0, startPos - firstSegment.start);
					firstSegment.labels
						.filter((l) => l.interval.end > startPos - firstSegment.start)
						.forEach((l) => {
							this.labelsById.delete(l.id);
							this.segmentIdsByLabelId.delete(l.id);
						});
					firstSegment.labels = firstSegment.labels.filter(
						(l) => l.interval.end <= startPos - firstSegment.start,
					);
					this.bounds[startIdx].end = startPos;
				}
				if (endPos - lastSegment.start === lastSegment.text.length) {
					lastSegment.labels.forEach((l) => {
						this.labelsById.delete(l.id);
						this.segmentIdsByLabelId.delete(l.id);
					});
					this.segmentsById.delete(affectedBounds[affectedBounds.length - 1].id);
					lastDeleted = true;
				} else {
					lastSegment.text = lastSegment.text.slice(endPos - lastSegment.start);
					lastSegment.labels
						.filter((l) => l.interval.start < endPos - lastSegment.start)
						.forEach((l) => {
							this.labelsById.delete(l.id);
							this.segmentIdsByLabelId.delete(l.id);
						});
					lastSegment.labels = lastSegment.labels
						.filter((l) => l.interval.start >= endPos - lastSegment.start)
						.map((l) => {
							const interval = {
								start: l.interval.start - (endPos - lastSegment.start),
								end: l.interval.end - (endPos - lastSegment.start),
							};
							this.labelsById.get(l.id)!.interval = interval;
							return { ...l, interval };
						});
					lastSegment.start = startPos;
					this.bounds[endIdx - 1].start = startPos;
					this.bounds[endIdx - 1].end -= endPos - lastSegment.start;
				}
				let killStart = startIdx + 1;
				let killEnd = endIdx - 1;
				if (firstDeleted) {
					killStart = startIdx;
				}
				if (lastDeleted) {
					killEnd = endIdx;
				}
				this.bounds.splice(killStart, killEnd - killStart);
				this.bounds.slice(killStart + (lastDeleted ? 0 : 1)).forEach((b) => {
					b.start -= length;
					b.end -= length;
					this.segmentsById.get(b.id)!.start -= length;
				});
				if (killStart - 1 >= 0 && killStart < this.bounds.length) {
					const rightDown = Math.min(
						this.bounds[killStart].end - this.bounds[killStart].start,
						...this.getSegment(this.bounds[killStart].id).labels.map(
							(l) => l.interval.start,
						),
					);
					const leftUp = Math.max(
						0,
						...this.getSegment(this.bounds[killStart - 1].id).labels.map(
							(l) => l.interval.end,
						),
					);
					if (
						rightDown +
							this.bounds[killStart].start -
							this.bounds[killStart - 1].start -
							leftUp <
						gap
					) {
						this.mergeSegments(killStart - 1, killStart + 1);
					}
				}
			}
			this.notifySubscribers();
		},

		batch(operations: () => void) {
			this.lock.acquire();
			try {
				operations();
			} finally {
				this.lock.release();
				this.notifySubscribers();
			}
		},
	};
	const segments = segmenter(initialText, initialLabels);
	for (const segment of segments) {
		segmentManager.postpendSegment(segment);
		for (const label of segment.labels) {
			segmentManager.labelsById.set(label.id, label);
		}
	}
	return segmentManager;
}
