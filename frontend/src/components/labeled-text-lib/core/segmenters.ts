import {
  type Style,
  type StyledLabel,
  type Segmenter,
  type Segment,
  type ReducingSegmenter,
  type FullReducingSegmenter,
  asReducedSegment,
  asFullReducedSegment,
} from "./types";

function isSorted(nums: number[]): boolean {
  for (let i = 1; i < nums.length; i++) {
    if (nums[i] < nums[i - 1]) {
      return false;
    }
  }
  return true;
}

export function makeBasicSegmenter<S extends Style, L extends StyledLabel<S>>(
  gap: number = 0,
): Segmenter<S, L> {
  return (text: string, labels: L[]): Segment<S, L>[] => {
    const segments: Segment<S, L>[] = [];
    const labelsCopy = [...labels];
    if (!isSorted(labelsCopy.map((l) => l.interval.start))) {
      labelsCopy.sort((a, b) => a.interval.start - b.interval.start);
    }
    let curSegmentStart = 0;
    let curSegmentEnd = 0;
    let curSegmentLabels: L[] = [];
    for (const label of labelsCopy) {
      // check if no overlap with the current segment
      if (label.interval.start >= curSegmentEnd + gap) {
        if (curSegmentEnd > curSegmentStart) {
          segments.push({
            labels: curSegmentLabels,
            start: curSegmentStart,
            text: text.slice(curSegmentStart, curSegmentEnd),
          });
        }
        if (label.interval.start > curSegmentEnd) {
          // add a segment for the gap
          segments.push({
            labels: [],
            start: curSegmentEnd,
            text: text.slice(curSegmentEnd, label.interval.start),
          });
        }
        curSegmentStart = label.interval.start;
        curSegmentEnd = label.interval.end;
        curSegmentLabels = [
          {
            ...label,
            interval: { start: 0, end: label.interval.end - label.interval.start },
          },
        ]; // adjust the label range to be relative to the segment start
      } else {
        // merge with the current segment
        curSegmentEnd = Math.max(curSegmentEnd, label.interval.end);
        curSegmentLabels.push({
          ...label,
          interval: {
            start: label.interval.start - curSegmentStart,
            end: label.interval.end - curSegmentStart,
          },
        }); // adjust the label range to be relative to the segment start
      }
    }
    if (curSegmentLabels.length > 0) {
      segments.push({
        labels: curSegmentLabels,
        start: curSegmentStart,
        text: text.slice(curSegmentStart, curSegmentEnd),
      });
    }
    if (curSegmentEnd < text.length) {
      segments.push({
        labels: [],
        start: curSegmentEnd,
        text: text.slice(curSegmentEnd),
      });
    }
    return segments;
  };
}

/**
 * Reduces the styles of all labels covering a region into one output style.
 * Implementations should define how to handle an empty list when unlabeled
 * segments are possible.
 */
export type StyleReducer<S extends Style> = (styles: S[]) => S;

export function makeReducingSegmenter<S extends Style, L extends StyledLabel<S>>(
  reducer: StyleReducer<S>,
  baseSegmenter: Segmenter<S, L>,
): ReducingSegmenter<S, L> {
  return (text: string, labels: L[]) => {
    const segments = baseSegmenter(text, labels);
    const newSegments: Segment<S, StyledLabel<S>>[] = [];
    for (const segment of segments) {
      const partition = new Set<number>();
      partition.add(0);
      if (segment.text.length === 0) {
        newSegments.push(segment);
        continue;
      }
      for (const label of segment.labels) {
        partition.add(label.interval.start);
        partition.add(label.interval.end);
      }
      partition.add(segment.text.length);
      const sortedPartition = Array.from(partition).sort((a, b) => a - b);
      const newLabels: StyledLabel<S>[] = [];
      for (let i = 0; i < sortedPartition.length - 1; i++) {
        const partStart = sortedPartition[i];
        const partEnd = sortedPartition[i + 1];
        const partLabels = segment.labels.filter((label) => {
          return label.interval.start <= partStart && label.interval.end >= partEnd;
        });
        newLabels.push({
          interval: { start: partStart, end: partEnd },
          style: reducer(partLabels.map((l) => l.style)),
        });
      }
      newSegments.push({
        start: segment.start,
        text: segment.text,
        labels: newLabels,
      });
    }
    return newSegments.map(asReducedSegment);
  };
}

export function makeFullReducingSegmenter<S extends Style, L extends StyledLabel<S>>(
  reducer: StyleReducer<S>,
): FullReducingSegmenter<S, L> {
  return (text: string, labels: L[]) => {
    const partition = new Set<number>();
    partition.add(0);
    partition.add(text.length);
    for (const label of labels) {
      partition.add(label.interval.start);
      partition.add(label.interval.end);
    }
    const sortedPartition = Array.from(partition).sort((a, b) => a - b);
    const segments: Segment<S, StyledLabel<S>>[] = [];
    for (let i = 0; i < sortedPartition.length - 1; i++) {
      const partStart = sortedPartition[i];
      const partEnd = sortedPartition[i + 1];
      const partLabels = labels.filter((label) => {
        return label.interval.start <= partStart && label.interval.end >= partEnd;
      });
      segments.push({
        start: partStart,
        text: text.slice(partStart, partEnd),
        labels:
          partLabels.length > 0
            ? [
                {
                  interval: { start: 0, end: partEnd - partStart },
                  style: reducer(partLabels.map((l) => l.style)),
                },
              ]
            : [],
      });
    }
    return segments.map(asFullReducedSegment);
  };
}
