import React, { useCallback } from "react";
import { type Label } from "../../types/label";
import { type LabelSourceConfig, buildMultiSourceSegments, resolveSegmentStyle } from "./labelOps";

type TextSelection = {
    startPos: number;
    endPos: number;
    text: string;
    rect: DOMRect;
};

type AnnotatedTextProps = {
    text: string;
    sources: LabelSourceConfig[];
    highlightedLabelId?: string | null;
    onLabelClick?: (label: Label, rect: DOMRect) => void;
    onTextSelect?: (selection: TextSelection) => void;
};

const getCharOffset = (node: Node, offsetInNode: number): number | null => {
    let el: HTMLElement | null = node instanceof HTMLElement ? node : node.parentElement;
    while (el && !el.dataset.charStart) {
        el = el.parentElement;
    }
    if (!el?.dataset.charStart) return null;
    return parseInt(el.dataset.charStart) + offsetInNode;
};

export const AnnotatedText: React.FC<AnnotatedTextProps> = ({
    text,
    sources,
    highlightedLabelId = null,
    onLabelClick,
    onTextSelect,
}) => {
    const segments = buildMultiSourceSegments(text, sources);

    const handleMouseUp = useCallback(() => {
        if (!onTextSelect) return;
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed || !sel.anchorNode || !sel.focusNode) return;

        const anchorOffset = getCharOffset(sel.anchorNode, sel.anchorOffset);
        const focusOffset = getCharOffset(sel.focusNode, sel.focusOffset);
        if (anchorOffset === null || focusOffset === null) return;

        const startPos = Math.min(anchorOffset, focusOffset);
        const endPos = Math.max(anchorOffset, focusOffset);
        if (startPos === endPos) return;

        const selectedText = text.slice(startPos, endPos);
        const range = sel.getRangeAt(0);
        const rect = range.getBoundingClientRect();

        sel.removeAllRanges();
        onTextSelect({ startPos, endPos, text: selectedText, rect });
    }, [onTextSelect, text]);

    return (
        <div onMouseUp={handleMouseUp} style={{
            flex: 1,
            overflow: "auto",
            padding: "20px",
            whiteSpace: "pre-wrap",
            textAlign: "left",
            position: "relative",
            fontFamily: "serif",
            fontSize: "1.05rem",
            lineHeight: 1.8,
        }}>
            {segments.map((seg) => {
                if (seg.activeSources.length === 0) {
                    return (
                        <span key={`p-${seg.charStart}`} data-char-start={seg.charStart} data-char-end={seg.charEnd}>
                            {seg.text}
                        </span>
                    );
                }

                const { css, interactiveSource } = resolveSegmentStyle(seg.activeSources);
                const labelForData = interactiveSource?.label ?? seg.activeSources[0].label;
                const key = `${seg.charStart}-${seg.charEnd}`;
                const isHighlighted = interactiveSource
                    ? highlightedLabelId === `${interactiveSource.label.labelStart}-${interactiveSource.label.labelEnd}`
                    : false;

                return (
                    <span
                        key={`s-${key}`}
                        data-char-start={seg.charStart}
                        data-char-end={seg.charEnd}
                        data-label-start={labelForData.labelStart}
                        data-label-end={labelForData.labelEnd}
                        title={seg.activeSources.map((s) =>
                            `${s.sourceKey}: ${s.label.labelEntityGroup ?? "?"} | score: ${s.label.labelScore.toFixed(2)}`
                        ).join("\n")}
                        onClick={(e) => {
                            if (interactiveSource && onLabelClick) {
                                onLabelClick(interactiveSource.label, (e.currentTarget as HTMLElement).getBoundingClientRect());
                            }
                        }}
                        style={{
                            ...css,
                            transition: "background-color 0.2s",
                            animation: isHighlighted ? "label-flash 1.5s ease-out" : undefined,
                        }}
                    >
                        {seg.text}
                    </span>
                );
            })}
            <style>{`
                @keyframes label-flash {
                    0%, 30% { background-color: rgba(255, 255, 0, 0.5); }
                    100% { background-color: transparent; }
                }
            `}</style>
        </div>
    );
};
