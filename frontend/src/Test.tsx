import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
    type CSSProperties,
    type JSX,
    type ReactNode,
    type RefObject,
} from "react";

import {
    makeBasicSegmentManager,
    type ManagedLabel,
    type SegmentManager,
} from "./components/labeled-text-lib/core/segmentManager";
import type { StyledLabel } from "./components/labeled-text-lib/core/types";
import { DynamicLabeledText } from "./components/labeled-text-lib/react/DynamicLabeledText";
import { makePlainBoxRenderer } from "./components/labeled-text-lib/react/Renderer";

type DemoStyle = {
    color: string;
};

type DemoLabel = StyledLabel<DemoStyle> & {
    name: string;
};

type DemoCaret = {
    anchor: number;
    focus: number;
    visible: boolean;
};

type EditorRect = {
    left: number;
    top: number;
    width: number;
    height: number;
};

type CaretPositionLike = {
    offsetNode: Node;
    offset: number;
};

type CaretRangeDocument = Document & {
    caretPositionFromPoint?: (x: number, y: number) => CaretPositionLike | null;
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
};

const demoText =
    "Alice met Bob in Wonderland.\nClick around, drag to select, type to edit, and add labels from the current selection.";

const demoLabels: ManagedLabel<DemoStyle, DemoLabel>[] = [
    {
        id: "alice",
        name: "Alice",
        interval: { start: 0, end: 5 },
        style: { color: "#f59e0b" },
    },
    {
        id: "bob",
        name: "Bob",
        interval: { start: 10, end: 13 },
        style: { color: "#38bdf8" },
    },
    {
        id: "wonderland",
        name: "Wonderland",
        interval: { start: 17, end: 27 },
        style: { color: "#8b5cf6" },
    },
];

const labelPalette = ["#f97316", "#10b981", "#6366f1", "#ec4899", "#0ea5e9", "#eab308"];

function clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(value, max));
}

function normalizeSelection(caret: DemoCaret): { start: number; end: number } {
    return {
        start: Math.min(caret.anchor, caret.focus),
        end: Math.max(caret.anchor, caret.focus),
    };
}

function getClosestSegmentElement(target: EventTarget | null): HTMLElement | null {
    if (!(target instanceof Element)) {
        return null;
    }
    return target.closest("[data-segment-start]") as HTMLElement | null;
}

function getSegmentElementByStart(
    containerRef: RefObject<HTMLDivElement | null>,
    start: number,
): HTMLElement | null {
    return containerRef.current?.querySelector(`[data-segment-start="${start}"]`) as HTMLElement | null;
}

function resolveTextOffset(container: HTMLElement, node: Node, offset: number): number {
    const range = container.ownerDocument.createRange();
    range.setStart(container, 0);
    try {
        range.setEnd(node, offset);
    } catch {
        return container.textContent?.length ?? 0;
    }
    return range.toString().length;
}

function resolveOffsetFromPoint(container: HTMLElement, clientX: number, clientY: number): number {
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

function resolveTextPointInElement(
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

function resolvePointerPosition<S extends object, L extends StyledLabel<S>>(
    eventTarget: EventTarget | null,
    clientX: number,
    clientY: number,
    manager: SegmentManager<S, L>,
): number {
    const textLength = manager.getText().length;
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

function collectAbsoluteLabels(manager: SegmentManager<DemoStyle, DemoLabel>): ManagedLabel<DemoStyle, DemoLabel>[] {
    const seen = new Set<string>();
    const labels: ManagedLabel<DemoStyle, DemoLabel>[] = [];

    for (const segment of manager.getSegments()) {
        for (const label of segment.labels) {
            if (seen.has(label.id)) {
                continue;
            }
            seen.add(label.id);
            labels.push({
                ...label,
                interval: {
                    start: segment.start + label.interval.start,
                    end: segment.start + label.interval.end,
                },
            });
        }
    }

    return labels.sort((left, right) => left.interval.start - right.interval.start);
}

function selectionText(text: string, caret: DemoCaret): string {
    const { start, end } = normalizeSelection(caret);
    return text.slice(start, end);
}

function insertTextAtSelection(
    manager: SegmentManager<DemoStyle, DemoLabel>,
    caret: DemoCaret,
    text: string,
    setCaret: (next: DemoCaret) => void,
) {
    const { start, end } = normalizeSelection(caret);
    if (end > start) {
        manager.deleteTextAt(start, end - start);
    }
    manager.insertTextAt(start, text);
    const nextPos = start + text.length;
    setCaret({ anchor: nextPos, focus: nextPos, visible: true });
}

function deleteSelectionOrBackspace(
    manager: SegmentManager<DemoStyle, DemoLabel>,
    caret: DemoCaret,
    setCaret: (next: DemoCaret) => void,
) {
    const { start, end } = normalizeSelection(caret);
    if (end > start) {
        manager.deleteTextAt(start, end - start);
        setCaret({ anchor: start, focus: start, visible: true });
        return true;
    }

    if (start > 0) {
        manager.deleteTextAt(start - 1, 1);
        const nextPos = start - 1;
        setCaret({ anchor: nextPos, focus: nextPos, visible: true });
        return true;
    }

    return false;
}

function deleteSelectionOrForwardDelete(
    manager: SegmentManager<DemoStyle, DemoLabel>,
    caret: DemoCaret,
    setCaret: (next: DemoCaret) => void,
) {
    const { start, end } = normalizeSelection(caret);
    if (end > start) {
        manager.deleteTextAt(start, end - start);
        setCaret({ anchor: start, focus: start, visible: true });
        return true;
    }

    if (start < manager.getText().length) {
        manager.deleteTextAt(start, 1);
        setCaret({ anchor: start, focus: start, visible: true });
        return true;
    }

    return false;
}

function findWordBounds(text: string, pos: number): { start: number; end: number } {
    if (text.length === 0) {
        return { start: 0, end: 0 };
    }

    const safePos = clamp(pos, 0, text.length);
    const charAtPos = safePos < text.length ? text[safePos] : text[safePos - 1];
    const isWordChar = (value: string | undefined) => Boolean(value && /[A-Za-z0-9_]/.test(value));

    if (!isWordChar(charAtPos)) {
        return { start: safePos, end: safePos };
    }

    let start = safePos;
    let end = safePos;

    while (start > 0 && isWordChar(text[start - 1])) {
        start -= 1;
    }
    while (end < text.length && isWordChar(text[end])) {
        end += 1;
    }

    return { start, end };
}

function measureSelectionRects(
    manager: SegmentManager<DemoStyle, DemoLabel>,
    caret: DemoCaret,
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

    for (const segment of manager.getSegments()) {
        const segmentStart = segment.start;
        const segmentEnd = segment.start + segment.text.length;
        const selectionStart = Math.max(start, segmentStart);
        const selectionEnd = Math.min(end, segmentEnd);
        const touchesCollapsedBoundary = isCollapsed && start >= segmentStart && start <= segmentEnd;

        if (!touchesCollapsedBoundary && selectionStart >= selectionEnd) {
            continue;
        }

        const segmentElement = getSegmentElementByStart(containerRef, segment.start);
        if (!segmentElement) {
            continue;
        }

        const localStart = isCollapsed ? start - segmentStart : selectionStart - segmentStart;
        const localEnd = isCollapsed ? start - segmentStart : selectionEnd - segmentStart;
        const startPoint = resolveTextPointInElement(segmentElement, localStart);
        const endPoint = resolveTextPointInElement(segmentElement, localEnd);
        if (!startPoint || !endPoint) {
            continue;
        }

        const range = segmentElement.ownerDocument.createRange();
        range.setStart(startPoint.node, startPoint.offset);
        range.setEnd(endPoint.node, endPoint.offset);

        const clientRects = Array.from(range.getClientRects());
        if (clientRects.length > 0) {
            rects.push(...clientRects.map((rect) => ({
                left: rect.left - overlayRect.left,
                top: rect.top - overlayRect.top,
                width: rect.width,
                height: rect.height,
            })));
            continue;
        }

        const rect = range.getBoundingClientRect();
        if (rect.height > 0) {
            rects.push({
                left: rect.left - overlayRect.left,
                top: rect.top - overlayRect.top,
                width: rect.width,
                height: rect.height,
            });
        }
    }

    return rects;
}

function makeDemoManager(): SegmentManager<DemoStyle, DemoLabel> {
    return makeBasicSegmentManager<DemoStyle, DemoLabel>(demoText, demoLabels, 1);
}

function Test() {
    const [manager] = useState(makeDemoManager);
    const [caret, setCaret] = useState<DemoCaret>({ anchor: 0, focus: 0, visible: false });
    const [textSnapshot, setTextSnapshot] = useState(() => manager.getText());
    const [eventLog, setEventLog] = useState<string[]>([]);
    const [editorActive, setEditorActive] = useState(false);
    const editorRootRef = useRef<HTMLDivElement | null>(null);
    const dragAnchorRef = useRef<number | null>(null);
    const nextLabelIdRef = useRef(0);
    const nextColorIndexRef = useRef(0);

    useEffect(() => {
        return manager.subscribe(() => {
            setTextSnapshot(manager.getText());
        });
    }, [manager]);

    useEffect(() => {
        const handlePointerDown = (event: PointerEvent) => {
            if (!editorRootRef.current) {
                return;
            }
            if (!editorRootRef.current.contains(event.target as Node)) {
                setEditorActive(false);
                setCaret((previous) => ({ ...previous, visible: false }));
            }
        };

        window.addEventListener("pointerdown", handlePointerDown);
        return () => {
            window.removeEventListener("pointerdown", handlePointerDown);
        };
    }, []);

    const pushEvent = useCallback((label: string) => {
        setEventLog((previous) => [label, ...previous].slice(0, 10));
    }, []);

    const renderCaret = useCallback(
        (
            {
                caret: currentCaret,
                containerRef,
                overlayRef,
            }: {
                caret: DemoCaret;
                containerRef: RefObject<HTMLDivElement | null>;
                overlayRef: RefObject<HTMLDivElement | null>;
            },
        ): JSX.Element => {
            const rects = measureSelectionRects(manager, currentCaret, containerRef, overlayRef);
            if (rects.length === 0) {
                return <></>;
            }

            const { start, end } = normalizeSelection(currentCaret);
            const isCollapsed = start === end;

            if (isCollapsed) {
                const rect = rects[0];
                return (
                    <div
                        style={{
                            position: "absolute",
                            left: rect.left,
                            top: rect.top,
                            width: 2,
                            height: rect.height || 18,
                            background: "#0f172a",
                            borderRadius: 999,
                            opacity: currentCaret.visible ? 1 : 0,
                        }}
                    />
                );
            }

            return (
                <>
                    {rects.map((rect, index) => (
                        <div
                            key={`${rect.left}:${rect.top}:${index}`}
                            style={{
                                position: "absolute",
                                left: rect.left,
                                top: rect.top,
                                width: Math.max(rect.width, 2),
                                height: rect.height,
                                background: "rgba(59, 130, 246, 0.22)",
                                borderRadius: 4,
                            }}
                        />
                    ))}
                </>
            );
        },
        [manager],
    );

    const renderer = useMemo(() => ({
        ...makePlainBoxRenderer<DemoStyle, DemoLabel>((style) => ({
            backgroundColor: `${style.color}28`,
            border: `1px solid ${style.color}5c`,
            borderRadius: "0.45rem",
        })),
        renderCaret,
    }), [renderCaret]);

    const addSelectionLabel = useCallback(() => {
        const { start, end } = normalizeSelection(caret);
        if (start === end) {
            pushEvent("add label skipped: empty selection");
            return;
        }

        const labelText = manager.getText().slice(start, end);
        const color = labelPalette[nextColorIndexRef.current % labelPalette.length];
        nextColorIndexRef.current += 1;
        const id = `selection-${nextLabelIdRef.current}`;
        nextLabelIdRef.current += 1;

        manager.addLabel(id, {
            name: labelText,
            interval: { start, end },
            style: { color },
        });

        pushEvent(`add label: "${labelText}"`);
    }, [caret, manager, pushEvent]);

    const clearIntersectingLabels = useCallback(() => {
        const { start, end } = normalizeSelection(caret);
        const selectedStart = start;
        const selectedEnd = end === start ? start + 1 : end;
        const labelIds = collectAbsoluteLabels(manager)
            .filter((label) => label.interval.start < selectedEnd && label.interval.end > selectedStart)
            .map((label) => label.id);

        if (labelIds.length === 0) {
            pushEvent("clear labels skipped: none intersect selection");
            return;
        }

        for (const id of labelIds) {
            manager.removeLabel(id);
        }

        pushEvent(`removed ${labelIds.length} label(s)`);
    }, [caret, manager, pushEvent]);

    const labels = collectAbsoluteLabels(manager);
    const selection = normalizeSelection(caret);
    const selectedText = selectionText(textSnapshot, caret);

    useEffect(() => {
        if (!editorActive) {
            return;
        }

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.defaultPrevented) {
                return;
            }

            const currentText = manager.getText();
            const currentCaret = caret;
            const textLength = currentText.length;
            const extend = event.shiftKey;
            const baseStart = Math.min(currentCaret.anchor, currentCaret.focus);
            const baseEnd = Math.max(currentCaret.anchor, currentCaret.focus);

            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "a") {
                event.preventDefault();
                setCaret({ anchor: 0, focus: textLength, visible: true });
                pushEvent("select all");
                return;
            }

            if ((event.metaKey || event.ctrlKey || event.altKey) && event.key.length === 1) {
                return;
            }

            if (event.key === "ArrowLeft") {
                event.preventDefault();
                const nextPos = clamp(
                    extend ? currentCaret.focus - 1 : baseStart - 1,
                    0,
                    textLength,
                );
                setCaret(
                    extend
                        ? { anchor: currentCaret.anchor, focus: nextPos, visible: true }
                        : { anchor: nextPos, focus: nextPos, visible: true },
                );
                return;
            }

            if (event.key === "ArrowRight") {
                event.preventDefault();
                const nextPos = clamp(
                    extend ? currentCaret.focus + 1 : baseEnd + 1,
                    0,
                    textLength,
                );
                setCaret(
                    extend
                        ? { anchor: currentCaret.anchor, focus: nextPos, visible: true }
                        : { anchor: nextPos, focus: nextPos, visible: true },
                );
                return;
            }

            if (event.key === "Home") {
                event.preventDefault();
                setCaret(
                    extend
                        ? { anchor: currentCaret.anchor, focus: 0, visible: true }
                        : { anchor: 0, focus: 0, visible: true },
                );
                return;
            }

            if (event.key === "End") {
                event.preventDefault();
                setCaret(
                    extend
                        ? { anchor: currentCaret.anchor, focus: textLength, visible: true }
                        : { anchor: textLength, focus: textLength, visible: true },
                );
                return;
            }

            if (event.key === "Backspace") {
                event.preventDefault();
                if (deleteSelectionOrBackspace(manager, currentCaret, setCaret)) {
                    pushEvent("backspace");
                }
                return;
            }

            if (event.key === "Delete") {
                event.preventDefault();
                if (deleteSelectionOrForwardDelete(manager, currentCaret, setCaret)) {
                    pushEvent("delete");
                }
                return;
            }

            if (event.key === "Enter") {
                event.preventDefault();
                insertTextAtSelection(manager, currentCaret, "\n", setCaret);
                pushEvent("insert line break");
                return;
            }

            if (event.key === "Tab") {
                event.preventDefault();
                insertTextAtSelection(manager, currentCaret, "    ", setCaret);
                pushEvent("insert tab");
                return;
            }

            if (event.key.length === 1) {
                event.preventDefault();
                insertTextAtSelection(manager, currentCaret, event.key, setCaret);
                pushEvent(`insert "${event.key}"`);
            }
        };

        const handlePaste = (event: ClipboardEvent) => {
            const pastedText = event.clipboardData?.getData("text/plain");
            if (!pastedText) {
                return;
            }
            event.preventDefault();
            insertTextAtSelection(manager, caret, pastedText, setCaret);
            pushEvent(`paste ${JSON.stringify(pastedText)}`);
        };

        const handleCopy = (event: ClipboardEvent) => {
            const copiedText = selectionText(manager.getText(), caret);
            if (!copiedText) {
                return;
            }
            event.preventDefault();
            event.clipboardData?.setData("text/plain", copiedText);
            pushEvent(`copy ${JSON.stringify(copiedText)}`);
        };

        const handleCut = (event: ClipboardEvent) => {
            const copiedText = selectionText(manager.getText(), caret);
            if (!copiedText) {
                return;
            }
            event.preventDefault();
            event.clipboardData?.setData("text/plain", copiedText);
            deleteSelectionOrBackspace(manager, caret, setCaret);
            pushEvent(`cut ${JSON.stringify(copiedText)}`);
        };

        window.addEventListener("keydown", handleKeyDown);
        window.addEventListener("paste", handlePaste);
        window.addEventListener("copy", handleCopy);
        window.addEventListener("cut", handleCut);

        return () => {
            window.removeEventListener("keydown", handleKeyDown);
            window.removeEventListener("paste", handlePaste);
            window.removeEventListener("copy", handleCopy);
            window.removeEventListener("cut", handleCut);
        };
    }, [caret, editorActive, manager, pushEvent]);

    return (
        <main
            style={{
                minHeight: "100vh",
                padding: "2rem",
                background: "#f8fafc",
                color: "#0f172a",
                fontFamily: "Inter, system-ui, sans-serif",
            }}
        >
            <div ref={editorRootRef} style={{ maxWidth: 1080, margin: "0 auto", display: "grid", gap: "1rem" }}>
                <section>
                    <h1 style={{ margin: 0, fontSize: "1.4rem" }}>DynamicLabeledText Editor POC</h1>
                    <p style={{ margin: "0.5rem 0 0", color: "#475569" }}>
                        Click, drag, type, backspace, paste, copy, cut, and add labels from the current selection.
                    </p>
                </section>

                <section
                    style={{
                        display: "flex",
                        gap: "0.75rem",
                        flexWrap: "wrap",
                    }}
                >
                    <button type="button" onClick={addSelectionLabel} style={buttonStyle}>
                        Add Label From Selection
                    </button>
                    <button type="button" onClick={clearIntersectingLabels} style={buttonStyle}>
                        Remove Intersecting Labels
                    </button>
                </section>

                <section
                    style={{
                        padding: "1rem",
                        border: "1px solid #cbd5e1",
                        borderRadius: 10,
                        background: "#ffffff",
                    }}
                >
                    <DynamicLabeledText
                        caret={caret}
                        manager={manager}
                        render={renderer}
                        containerStyle={{
                            minHeight: "9rem",
                            padding: "0.75rem 1rem",
                            border: "1px solid #cbd5e1",
                            borderRadius: 8,
                            background: "#ffffff",
                            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                            fontSize: "1rem",
                            lineHeight: 1.65,
                            whiteSpace: "pre-wrap",
                            userSelect: "none",
                            cursor: "text",
                        }}
                        onPointerDown={({ event, manager: currentManager }) => {
                            event.preventDefault();
                            setEditorActive(true);
                            const pos = resolvePointerPosition(
                                event.target,
                                event.clientX,
                                event.clientY,
                                currentManager,
                            );
                            dragAnchorRef.current = pos;
                            setCaret({ anchor: pos, focus: pos, visible: true });
                            pushEvent(`pointer down @ ${pos}`);
                        }}
                        onPointerMove={({ event, manager: currentManager }) => {
                            if (dragAnchorRef.current === null || event.buttons === 0) {
                                return;
                            }
                            const pos = resolvePointerPosition(
                                event.target,
                                event.clientX,
                                event.clientY,
                                currentManager,
                            );
                            setCaret({ anchor: dragAnchorRef.current, focus: pos, visible: true });
                        }}
                        onPointerUp={({ event, manager: currentManager }) => {
                            if (dragAnchorRef.current === null) {
                                return;
                            }
                            const pos = resolvePointerPosition(
                                event.target,
                                event.clientX,
                                event.clientY,
                                currentManager,
                            );
                            setCaret({ anchor: dragAnchorRef.current, focus: pos, visible: true });
                            dragAnchorRef.current = null;
                            pushEvent(`pointer up @ ${pos}`);
                        }}
                        onDoubleClick={({ event, manager: currentManager }) => {
                            const pos = resolvePointerPosition(
                                event.target,
                                event.clientX,
                                event.clientY,
                                currentManager,
                            );
                            const bounds = findWordBounds(currentManager.getText(), pos);
                            setCaret({ anchor: bounds.start, focus: bounds.end, visible: true });
                            pushEvent(`double click word @ ${pos}`);
                        }}
                        onFocus={() => {
                            setEditorActive(true);
                            setCaret((previous) => ({ ...previous, visible: true }));
                            pushEvent("focus");
                        }}
                        onBlur={() => {
                            dragAnchorRef.current = null;
                            setEditorActive(false);
                            setCaret((previous) => ({ ...previous, visible: false }));
                            pushEvent("blur");
                        }}
                        onInput={({ event }) => {
                            event.currentTarget.textContent = "";
                        }}
                    />
                </section>

                <section
                    style={{
                        display: "grid",
                        gridTemplateColumns: "1.1fr 0.9fr",
                        gap: "1rem",
                    }}
                >
                    <InfoCard title="Editor State">
                        <StateRow label="text length" value={String(textSnapshot.length)} />
                        <StateRow label="selection" value={`[${selection.start}, ${selection.end})`} />
                        <StateRow label="selected text" value={selectedText ? JSON.stringify(selectedText) : "(none)"} />
                        <StateRow label="caret visible" value={String(caret.visible)} />
                        <StateRow label="editor active" value={String(editorActive)} />
                    </InfoCard>

                    <InfoCard title="Recent Events">
                        {eventLog.length === 0 ? (
                            <div style={{ color: "#64748b" }}>No events yet.</div>
                        ) : (
                            <div style={{ display: "grid", gap: "0.35rem", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}>
                                {eventLog.map((entry, index) => (
                                    <div key={`${entry}-${index}`}>{entry}</div>
                                ))}
                            </div>
                        )}
                    </InfoCard>
                </section>

                <InfoCard title="Labels">
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                        {labels.map((label) => (
                            <div
                                key={label.id}
                                style={{
                                    padding: "0.35rem 0.55rem",
                                    borderRadius: 999,
                                    border: `1px solid ${label.style.color}66`,
                                    background: `${label.style.color}18`,
                                    color: "#1e293b",
                                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                                    fontSize: "0.9rem",
                                }}
                            >
                                {label.name} [{label.interval.start}, {label.interval.end})
                            </div>
                        ))}
                    </div>
                </InfoCard>
            </div>
        </main>
    );
}

function InfoCard(
    {
        title,
        children,
    }: {
        title: string;
        children: ReactNode;
    },
) {
    return (
        <section
            style={{
                padding: "1rem",
                border: "1px solid #cbd5e1",
                borderRadius: 10,
                background: "#ffffff",
            }}
        >
            <h2 style={{ margin: 0, fontSize: "1rem" }}>{title}</h2>
            <div style={{ marginTop: "0.75rem", color: "#334155" }}>{children}</div>
        </section>
    );
}

function StateRow({ label, value }: { label: string; value: string }) {
    return (
        <div style={{ display: "grid", gridTemplateColumns: "8rem 1fr", gap: "0.75rem", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}>
            <strong style={{ fontWeight: 600 }}>{label}</strong>
            <span>{value}</span>
        </div>
    );
}

const buttonStyle: CSSProperties = {
    border: "1px solid #cbd5e1",
    background: "#ffffff",
    borderRadius: 8,
    padding: "0.55rem 0.8rem",
    font: "inherit",
    cursor: "pointer",
};

export { Test };
