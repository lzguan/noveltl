import type { RefObject } from "react";

import type { Chapter, DetailHttpErrorResponse, RequestConflictErrorResponse } from "@/client";
import type { Caret as EditorCaret } from "@/components/labeled-text-lib/react/DynamicLabeledText";

export type EditorRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type CaretPositionLike = {
  offsetNode: Node;
  offset: number;
};

export type CaretRangeDocument = Document & {
  caretPositionFromPoint?: (x: number, y: number) => CaretPositionLike | null;
  caretRangeFromPoint?: (x: number, y: number) => Range | null;
};

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(value, max));
}

export function getSuggestedChapterNumber(chapters: Chapter[]): number {
  if (chapters.length === 0) {
    return 1;
  }
  return Math.max(...chapters.map((chapter) => chapter.chapterNum)) + 1;
}

export function normalizeSelection(caret: EditorCaret): { start: number; end: number } {
  return {
    start: Math.min(caret.anchor, caret.focus),
    end: Math.max(caret.anchor, caret.focus),
  };
}

export function selectionText(text: string, caret: EditorCaret): string {
  const { start, end } = normalizeSelection(caret);
  return text.slice(start, end);
}

export function getClosestSegmentElement(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof Element)) {
    return null;
  }
  return target.closest("[data-segment-start]") as HTMLElement | null;
}

export function getSegmentElementByStart(
  containerRef: RefObject<HTMLDivElement | null>,
  start: number,
): HTMLElement | null {
  return containerRef.current?.querySelector(
    `[data-segment-start="${start}"]`,
  ) as HTMLElement | null;
}

export function resolveTextOffset(container: HTMLElement, node: Node, offset: number): number {
  const range = container.ownerDocument.createRange();
  range.setStart(container, 0);
  try {
    range.setEnd(node, offset);
  } catch {
    return container.textContent?.length ?? 0;
  }
  return range.toString().length;
}

export function resolveOffsetFromPoint(
  container: HTMLElement,
  clientX: number,
  clientY: number,
): number {
  const doc = container.ownerDocument as CaretRangeDocument;
  const caretPosition = doc.caretPositionFromPoint?.(clientX, clientY);
  if (caretPosition && container.contains(caretPosition.offsetNode)) {
    return resolveTextOffset(container, caretPosition.offsetNode, caretPosition.offset);
  }

  const caretRange = doc.caretRangeFromPoint?.(clientX, clientY);
  if (caretRange && container.contains(caretRange.startContainer)) {
    return resolveTextOffset(container, caretRange.startContainer, caretRange.startOffset);
  }

  return container.textContent?.length ?? 0;
}

export function resolveTextPointInElement(
  element: HTMLElement,
  offset: number,
): { node: Node; offset: number } | null {
  const walker = element.ownerDocument.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  let traversed = 0;
  let lastTextNode: Node | null = null;

  while (walker.nextNode()) {
    const node = walker.currentNode;
    const textLength = node.textContent?.length ?? 0;
    lastTextNode = node;
    if (offset <= traversed + textLength) {
      return {
        node,
        offset: offset - traversed,
      };
    }
    traversed += textLength;
  }

  if (!lastTextNode) {
    return null;
  }

  return {
    node: lastTextNode,
    offset: lastTextNode.textContent?.length ?? 0,
  };
}

export function resolvePointerPosition(
  eventTarget: EventTarget | null,
  clientX: number,
  clientY: number,
  textLength: number,
): number {
  const segmentElement = getClosestSegmentElement(eventTarget);
  if (!segmentElement) {
    return textLength;
  }

  const segmentStart = Number(segmentElement.getAttribute("data-segment-start"));
  if (Number.isNaN(segmentStart)) {
    return textLength;
  }

  const localOffset = clamp(
    resolveOffsetFromPoint(segmentElement, clientX, clientY),
    0,
    segmentElement.textContent?.length ?? 0,
  );

  return clamp(segmentStart + localOffset, 0, textLength);
}

export function isWordBoundaryCharacter(value: string | undefined): boolean {
  if (!value) {
    return true;
  }
  return /[\s.,;:!?()[\]{}"'`~\-–—/\\<>|@#$%^&*_+=，。！？；：、（）【】《》「」『』]/u.test(value);
}

export function findWordBounds(text: string, pos: number): { start: number; end: number } {
  if (text.length === 0) {
    return { start: 0, end: 0 };
  }

  const safePos = clamp(pos, 0, text.length);
  const anchorIndex = safePos < text.length ? safePos : Math.max(0, safePos - 1);
  const current = text[anchorIndex];
  if (isWordBoundaryCharacter(current)) {
    return { start: safePos, end: safePos };
  }

  let start = anchorIndex;
  let end = anchorIndex + 1;
  while (start > 0 && !isWordBoundaryCharacter(text[start - 1])) {
    start -= 1;
  }
  while (end < text.length && !isWordBoundaryCharacter(text[end])) {
    end += 1;
  }

  return { start, end };
}

export function measureSelectionRects(
  text: string,
  caret: EditorCaret,
  containerRef: RefObject<HTMLDivElement | null>,
  overlayRef: RefObject<HTMLDivElement | null>,
): EditorRect[] {
  const container = containerRef.current;
  const overlay = overlayRef.current;
  if (!container || !overlay || !caret.visible) {
    return [];
  }

  const overlayRect = overlay.getBoundingClientRect();
  const { start, end } = normalizeSelection(caret);
  const isCollapsed = start === end;
  const rects: EditorRect[] = [];

  const segmentElements = Array.from(
    container.querySelectorAll<HTMLElement>("[data-segment-start]"),
  );
  for (const segmentElement of segmentElements) {
    const segmentStart = Number(segmentElement.dataset.segmentStart ?? "0");
    const segmentLength = segmentElement.textContent?.length ?? 0;
    const segmentEnd = segmentStart + segmentLength;
    const selectionStart = Math.max(start, segmentStart);
    const selectionEnd = Math.min(end, segmentEnd);
    const touchesCollapsedBoundary = isCollapsed && start >= segmentStart && start <= segmentEnd;

    if (!touchesCollapsedBoundary && selectionStart >= selectionEnd) {
      continue;
    }

    const localStart = isCollapsed ? start - segmentStart : selectionStart - segmentStart;
    const localEnd = isCollapsed ? start - segmentStart : selectionEnd - segmentStart;
    const startPoint = resolveTextPointInElement(segmentElement, localStart);
    const endPoint = resolveTextPointInElement(segmentElement, localEnd);
    if (!startPoint || !endPoint) {
      continue;
    }

    const range = document.createRange();
    range.setStart(startPoint.node, startPoint.offset);
    range.setEnd(endPoint.node, endPoint.offset);

    const clientRects = Array.from(range.getClientRects());
    if (clientRects.length > 0) {
      rects.push(
        ...clientRects.map((rect) => ({
          left: rect.left - overlayRect.left,
          top: rect.top - overlayRect.top,
          width: rect.width,
          height: rect.height,
        })),
      );
      continue;
    }

    const rect = range.getBoundingClientRect();
    if (rect.height > 0 || isCollapsed) {
      rects.push({
        left: rect.left - overlayRect.left,
        top: rect.top - overlayRect.top,
        width: rect.width,
        height: rect.height,
      });
    }
  }

  if (rects.length > 0) {
    return rects;
  }

  const endSegment =
    text.length === 0 ? null : getSegmentElementByStart(containerRef, text.length - 1);
  if (!endSegment) {
    return [];
  }
  const fallbackRect = endSegment.getBoundingClientRect();
  return [
    {
      left: fallbackRect.right - overlayRect.left,
      top: fallbackRect.top - overlayRect.top,
      width: 0,
      height: fallbackRect.height,
    },
  ];
}

export function isDetailHttpErrorResponse(error: unknown): error is DetailHttpErrorResponse {
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { detail?: unknown }).detail === "string"
  );
}

export function isRequestConflictErrorResponse(
  error: unknown,
): error is RequestConflictErrorResponse {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const detail = (error as { detail?: unknown }).detail;
  return (
    typeof detail === "object" &&
    detail !== null &&
    typeof (detail as { detail?: unknown }).detail === "string" &&
    typeof (detail as { cacheConflict?: unknown }).cacheConflict === "boolean"
  );
}

export function formatUnknownError(error: unknown): string {
  if (isRequestConflictErrorResponse(error)) {
    return error.detail.detail;
  }
  if (isDetailHttpErrorResponse(error)) {
    return error.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "Something went wrong while loading the editor.";
}

export function extractErrorMessages(errors: Error[] | null): string[] {
  if (!errors) {
    return [];
  }
  return errors.map((error) => error.message);
}

export function isOutdatedError(error: Error): boolean {
  return error.message.toLowerCase().includes("outdated");
}
