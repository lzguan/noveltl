import { type Label, type LabelOp } from "../../types/label";

// --- Segment types ---

export type PlainSegment = {
    type: "plain";
    text: string;
    charStart: number;
    charEnd: number;
};

export type LabelSegment = {
    type: "label";
    text: string;
    charStart: number;
    charEnd: number;
    label: Label;
};

export type Segment = PlainSegment | LabelSegment;

// --- Build segments from text + labels ---

export const buildSegments = (text: string, labels: Label[]): Segment[] => {
    const sorted = [...labels].sort((a, b) => a.labelStart - b.labelStart);
    const segments: Segment[] = [];
    let cursor = 0;

    for (const label of sorted) {
        // Skip overlapping labels (label starts before cursor)
        if (label.labelStart < cursor) continue;

        // Plain text before this label
        if (label.labelStart > cursor) {
            segments.push({
                type: "plain",
                text: text.slice(cursor, label.labelStart),
                charStart: cursor,
                charEnd: label.labelStart,
            });
        }

        // Label span
        segments.push({
            type: "label",
            text: text.slice(label.labelStart, label.labelEnd),
            charStart: label.labelStart,
            charEnd: label.labelEnd,
            label,
        });

        cursor = label.labelEnd;
    }

    // Trailing plain text
    if (cursor < text.length) {
        segments.push({
            type: "plain",
            text: text.slice(cursor),
            charStart: cursor,
            charEnd: text.length,
        });
    }

    return segments;
};

// --- Entity group colors ---

const ENTITY_GROUP_COLORS: Record<string, string> = {
    PER: "#4a90d9",
    LOC: "#27ae60",
    ORG: "#e67e22",
    MISC: "#8e44ad",
};

const DEFAULT_COLOR = "#7f8c8d";

export const getEntityGroupColor = (group: string | null): string => {
    if (!group) return DEFAULT_COLOR;
    return ENTITY_GROUP_COLORS[group.toUpperCase()] ?? DEFAULT_COLOR;
};

// --- Apply label operations ---

export const applyOpToLabels = (labels: Label[], op: LabelOp): Label[] => {
    switch (op.op) {
        case "add":
            return [
                ...labels,
                {
                    labelEntityGroup: op.entityGroup ?? null,
                    labelScore: op.score ?? 1.0,
                    labelWord: op.word,
                    labelStart: op.startPos,
                    labelEnd: op.endPos,
                    labelDirty: op.dirty ?? true,
                },
            ];
        case "delete":
            return labels.filter(
                (l) => !(l.labelStart === op.startPos && l.labelEnd === op.endPos && l.labelWord === op.word)
            );
        case "update":
            return labels.map((l) => {
                if (l.labelStart !== op.startPos || l.labelEnd !== op.endPos || l.labelWord !== op.word) {
                    return l;
                }
                return {
                    ...l,
                    labelStart: op.newStartPos ?? l.labelStart,
                    labelEnd: op.newEndPos ?? l.labelEnd,
                    labelWord: op.newWord ?? l.labelWord,
                    labelDirty: op.dirty ?? l.labelDirty,
                    labelEntityGroup: op.entityGroup !== undefined ? op.entityGroup : l.labelEntityGroup,
                    labelScore: op.score ?? l.labelScore,
                };
            });
        default:
            return labels;
    }
};
