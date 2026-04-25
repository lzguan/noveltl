/* Abstract Types */


export type Style = object


/**
 * Half-open character range into the source text: [start, end).
 * `start` is inclusive and `end` is exclusive.
 */
export type Interval = {
    start: number;
    end: number;
};

/**
 * Source annotation over the full text.
 *
 * Label ranges are canonical document coordinates. Segmenters may project them
 * into segment-local coordinates in their output.
 */
export type StyledLabel<S extends Style> = {
    interval : Interval;
    style : S
}

/**
 * A disjoint rendered slice of text.
 *
 * Segments are ordered by `start` and are intended to partition some region of
 * the source text. For segment-local consumers, each label interval in `labels` is
 * relative to `segment.start`, not to the full document.
 */
export type Segment<S extends Style, L extends StyledLabel<S>> = {
    start : number;
    text : string;
    labels : L[];
}

declare const reducedBrand: unique symbol;
declare const fullReducedBrand: unique symbol;

export type ReducedSegment<S extends Style> = Segment<S, StyledLabel<S>> & { [reducedBrand] : true };

export function asReducedSegment<S extends Style>(segment: Segment<S, StyledLabel<S>>): ReducedSegment<S> {
    return segment as ReducedSegment<S>;
}

export type FullReducedSegment<S extends Style> = ReducedSegment<S> & { [fullReducedBrand] : true };

export function asFullReducedSegment<S extends Style>(segment: Segment<S, StyledLabel<S>>): FullReducedSegment<S> {
    return segment as FullReducedSegment<S>;
}

/**
 * Produces renderable text segments from source text and absolute labels.
 */
export type Segmenter<S extends Style, L extends StyledLabel<S>> = (text : string, labels : L[]) => Segment<S, L>[];

export type ReducingSegmenter<S extends Style, L extends StyledLabel<S>> = (text : string, labels : L[]) => ReducedSegment<S>[];

export type FullReducingSegmenter<S extends Style, L extends StyledLabel<S>> = (text : string, labels : L[]) => FullReducedSegment<S>[];
