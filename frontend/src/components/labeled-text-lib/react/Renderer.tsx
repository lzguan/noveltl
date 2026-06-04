import React, { useCallback, useEffect, useLayoutEffect, useState, type JSX } from "react";

import type {
  Segment,
  ReducedSegment,
  FullReducedSegment,
  Style,
  StyledLabel,
} from "../core/types";

export type TextRenderer<S extends Style, L extends StyledLabel<S>> = ({
  segment,
}: {
  segment: Segment<S, L>;
}) => JSX.Element;

export type ReducedTextRenderer<S extends Style> = ({
  segment,
}: {
  segment: ReducedSegment<S>;
}) => JSX.Element;

export type FullReducedTextRenderer<S extends Style> = ({
  segment,
}: {
  segment: FullReducedSegment<S>;
}) => JSX.Element;

export type OverlayRenderer<S extends Style, L extends StyledLabel<S>> = ({
  segment,
  containerRef,
  overlayRef,
}: {
  segment: Segment<S, L>;
  readonly containerRef: React.RefObject<HTMLDivElement | null>;
  overlayRef: React.RefObject<HTMLDivElement | null>;
}) => JSX.Element;

type TextPoint = {
  node: Node | null;
  pos: number;
};

type TextPointResolver<S extends Style, L extends StyledLabel<S>> = (
  element: HTMLElement | null, // container element
  segment: Segment<S, L>,
  offset: number, // offset into the segment text
) => TextPoint | null;

/**
 * Rendering strategy for a segmented text view.
 */
export type Renderer<S extends Style, L extends StyledLabel<S>> = {
  renderText: TextRenderer<S, L>;
  renderOverlay?: OverlayRenderer<S, L>;
};

export type ReducedRenderer<S extends Style, L extends StyledLabel<S>> = {
  renderText: ReducedTextRenderer<S>;
  renderOverlay?: OverlayRenderer<S, L>;
};

export type FullReducedRenderer<S extends Style, L extends StyledLabel<S>> = {
  renderText: FullReducedTextRenderer<S>;
  renderOverlay?: OverlayRenderer<S, L>;
};

export function makePlainTextRenderer<S extends Style, L extends StyledLabel<S>>(): TextRenderer<
  S,
  L
> {
  return ({ segment }) => {
    return <>{segment.text}</>;
  };
}

export function resolvePlainTextPoint<S extends Style, L extends StyledLabel<S>>(
  element: HTMLElement | null,
  _: Segment<S, L>,
  offset: number,
): TextPoint | null {
  return { node: element ? element.firstChild : null, pos: offset };
}

export function getSegmentElement<S extends Style, L extends StyledLabel<S>>(
  containerRef: React.RefObject<HTMLDivElement | null>,
  segment: Segment<S, L>,
): HTMLElement | null {
  return containerRef.current?.querySelector(
    `[data-segment-start="${segment.start}"]`,
  ) as HTMLElement | null;
}

export function makeBoxOverlayRenderer<S extends Style, L extends StyledLabel<S>>(
  toBoxStyle: (style: S) => React.CSSProperties,
  resolveTextPoint: TextPointResolver<S, L>,
): OverlayRenderer<S, L> {
  return ({ segment, containerRef, overlayRef }) => {
    const [styledBoxes, setStyledBoxes] = useState<
      { rect: { left: number; top: number; width: number; height: number }; style: S }[]
    >([]);

    const measure = useCallback(() => {
      const overlayElement = overlayRef.current;
      if (!overlayElement) {
        setStyledBoxes((prev) => (prev.length === 0 ? prev : []));
        return;
      }
      const overlayRect = overlayElement.getBoundingClientRect();
      const styledRects = segment.labels
        .map((label) => {
          const range = document.createRange();
          const segmentElement = getSegmentElement(containerRef, segment);
          if (!segmentElement) {
            return;
          }
          const leftTextPoint = resolveTextPoint(segmentElement, segment, label.interval.start);
          const rightTextPoint = resolveTextPoint(segmentElement, segment, label.interval.end);
          if (!leftTextPoint?.node || !rightTextPoint?.node) {
            return;
          }
          range.setStart(leftTextPoint.node, leftTextPoint.pos);
          range.setEnd(rightTextPoint.node, rightTextPoint.pos);
          return Array.from(range.getClientRects()).map((rect) => ({
            rect: {
              height: rect.height,
              width: rect.width,
              top: rect.top - overlayRect.top,
              left: rect.left - overlayRect.left,
            },
            style: label.style,
          }));
        })
        .flat()
        .filter((x): x is Exclude<typeof x, undefined> => x !== undefined);
      setStyledBoxes(styledRects);
    }, [segment, overlayRef, containerRef]);

    useLayoutEffect(() => {
      measure();
    }, [measure]);

    useEffect(() => {
      const segmentElement = getSegmentElement(containerRef, segment);
      if (!segmentElement) {
        return;
      }
      const overlayElement = overlayRef.current;
      if (!overlayElement) {
        return;
      }
      const resizeObserver = new ResizeObserver(() => {
        measure();
      });
      resizeObserver.observe(segmentElement);
      resizeObserver.observe(overlayElement);
      return () => {
        resizeObserver.disconnect();
      };
    }, [measure, segment, containerRef, overlayRef]);

    return (
      <>
        {styledBoxes.map(({ rect, style }, index) => (
          <div
            key={segment.start + ":" + index}
            style={{
              position: "absolute",
              left: rect.left,
              top: rect.top,
              width: rect.width,
              height: rect.height,
              pointerEvents: "none",
              ...toBoxStyle(style),
            }}
          />
        ))}
      </>
    );
  };
}

export function makePlainBoxRenderer<BS extends Style, L extends StyledLabel<BS>>(
  toBoxStyle: (style: BS) => React.CSSProperties,
): Renderer<BS, L> {
  return {
    renderText: makePlainTextRenderer(),
    renderOverlay: makeBoxOverlayRenderer(toBoxStyle, resolvePlainTextPoint),
  };
}
