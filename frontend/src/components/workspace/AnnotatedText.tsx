import React, { useCallback } from "react";
import { type Label } from "../../types/label";
import { buildSegments, getEntityGroupColor } from "./labelOps";

type TextSelection = {
    startPos: number;
    endPos: number;
    text: string;
    rect: DOMRect;
};

type AnnotatedTextProps = {
    text: string;
    labels: Label[];
    previewLabels?: Label[] | null;
    scoreThreshold?: number;
    highlightedLabelId?: string | null;
    onLabelClick?: (label: Label, rect: DOMRect) => void;
    onTextSelect?: (selection: TextSelection) => void;
};

const labelKey = (label: Label) => `${label.labelStart}-${label.labelEnd}`;

const getCharOffset = (node: Node, offsetInNode: number): number | null => {
    // Walk up to find nearest span with data-char-start
    let el: HTMLElement | null = node instanceof HTMLElement ? node : node.parentElement;
    while (el && !el.dataset.charStart) {
        el = el.parentElement;
    }
    if (!el?.dataset.charStart) return null;
    return parseInt(el.dataset.charStart) + offsetInNode;
};

export const AnnotatedText: React.FC<AnnotatedTextProps> = ({
    text,
    labels,
    previewLabels = null,
    scoreThreshold = 0,
    highlightedLabelId = null,
    onLabelClick,
    onTextSelect,
}) => {
    const segments = buildSegments(text, labels);
    const previewSegments = previewLabels ? buildSegments(text, previewLabels) : null;

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
            position: "relative",
            fontFamily: "serif",
            fontSize: "1.05rem",
            lineHeight: 1.8,
        }}>
            {segments.map((seg) => {
                if (seg.type === "plain") {
                    return (
                        <span key={`p-${seg.charStart}`} data-char-start={seg.charStart} data-char-end={seg.charEnd}>
                            {seg.text}
                        </span>
                    );
                }

                const { label } = seg;
                const color = getEntityGroupColor(label.labelEntityGroup);
                const key = labelKey(label);
                const dimmed = label.labelScore < scoreThreshold;
                const isHighlighted = highlightedLabelId === key;

                return (
                    <span
                        key={`l-${key}`}
                        data-char-start={seg.charStart}
                        data-char-end={seg.charEnd}
                        data-label-start={label.labelStart}
                        data-label-end={label.labelEnd}
                        title={`${label.labelEntityGroup ?? "?"} | score: ${label.labelScore.toFixed(2)}${label.labelDirty ? " | dirty" : ""}`}
                        onClick={(e) => {
                            if (onLabelClick) {
                                onLabelClick(label, (e.currentTarget as HTMLElement).getBoundingClientRect());
                            }
                        }}
                        style={{
                            backgroundColor: `${color}33`,
                            borderBottom: label.labelDirty ? `2px dotted ${color}` : `2px solid ${color}`,
                            opacity: dimmed ? 0.4 : 1,
                            cursor: onLabelClick ? "pointer" : "default",
                            borderRadius: "2px",
                            padding: "1px 0",
                            transition: "background-color 0.2s",
                            animation: isHighlighted ? "label-flash 1.5s ease-out" : undefined,
                        }}
                    >
                        {seg.text}
                    </span>
                );
            })}
            {previewSegments && (
                <div style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    padding: "20px",
                    whiteSpace: "pre-wrap",
                    fontFamily: "serif",
                    fontSize: "1.05rem",
                    lineHeight: 1.8,
                    pointerEvents: "none",
                }}>
                    {previewSegments.map((seg) => {
                        if (seg.type === "plain") {
                            return <span key={`pv-p-${seg.charStart}`} style={{ visibility: "hidden" }}>{seg.text}</span>;
                        }
                        const color = getEntityGroupColor(seg.label.labelEntityGroup);
                        return (
                            <span
                                key={`pv-l-${seg.charStart}-${seg.charEnd}`}
                                style={{
                                    backgroundColor: `${color}22`,
                                    borderBottom: `2px dashed ${color}`,
                                    opacity: 0.6,
                                    borderRadius: "2px",
                                    padding: "1px 0",
                                }}
                            >
                                {seg.text}
                            </span>
                        );
                    })}
                </div>
            )}
            <style>{`
                @keyframes label-flash {
                    0%, 30% { background-color: rgba(255, 255, 0, 0.5); }
                    100% { background-color: transparent; }
                }
            `}</style>
        </div>
    );
};
