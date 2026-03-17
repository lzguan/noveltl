import React from "react";
import { type Label } from "../../types/label";
import { buildSegments, getEntityGroupColor } from "./labelOps";

type AnnotatedTextProps = {
    text: string;
    labels: Label[];
    scoreThreshold?: number;
    highlightedLabelId?: string | null;
    onLabelClick?: (label: Label, rect: DOMRect) => void;
};

const labelKey = (label: Label) => `${label.labelStart}-${label.labelEnd}`;

export const AnnotatedText: React.FC<AnnotatedTextProps> = ({
    text,
    labels,
    scoreThreshold = 0,
    highlightedLabelId = null,
    onLabelClick,
}) => {
    const segments = buildSegments(text, labels);

    return (
        <div style={{
            flex: 1,
            overflow: "auto",
            padding: "20px",
            whiteSpace: "pre-wrap",
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
            <style>{`
                @keyframes label-flash {
                    0%, 30% { background-color: rgba(255, 255, 0, 0.5); }
                    100% { background-color: transparent; }
                }
            `}</style>
        </div>
    );
};
