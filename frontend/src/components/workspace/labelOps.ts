import { type CSSProperties } from "react";
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

// --- Multi-source label rendering ---

export const NER_RESULTS_COLOR = "#e84393";

export type LabelSourceConfig = {
    sourceKey: string;
    labels: Label[];
    style: "bright" | "dim";
    mode: "highlight" | "underline";
    interactive: boolean;
    priority: number;
};

export type ActiveSource = {
    sourceKey: string;
    label: Label;
    style: "bright" | "dim";
    mode: "highlight" | "underline";
    interactive: boolean;
    priority: number;
};

export type MultiSourceSegment = {
    text: string;
    charStart: number;
    charEnd: number;
    activeSources: ActiveSource[];
};

export const buildMultiSourceSegments = (text: string, sources: LabelSourceConfig[]): MultiSourceSegment[] => {
    // Collect all boundary points
    const boundaries = new Set<number>();
    boundaries.add(0);
    boundaries.add(text.length);

    for (const source of sources) {
        for (const label of source.labels) {
            if (label.labelStart >= 0 && label.labelStart <= text.length) boundaries.add(label.labelStart);
            if (label.labelEnd >= 0 && label.labelEnd <= text.length) boundaries.add(label.labelEnd);
        }
    }

    const sortedBoundaries = [...boundaries].sort((a, b) => a - b);
    if (sortedBoundaries.length < 2) return [];

    const segments: MultiSourceSegment[] = [];

    for (let i = 0; i < sortedBoundaries.length - 1; i++) {
        const start = sortedBoundaries[i];
        const end = sortedBoundaries[i + 1];
        if (start === end) continue;

        const activeSources: ActiveSource[] = [];

        for (const source of sources) {
            for (const label of source.labels) {
                if (label.labelStart <= start && label.labelEnd >= end) {
                    activeSources.push({
                        sourceKey: source.sourceKey,
                        label,
                        style: source.style,
                        mode: source.mode,
                        interactive: source.interactive,
                        priority: source.priority,
                    });
                    break; // Within-source overlaps don't happen (DB enforced)
                }
            }
        }

        // Sort by priority (lowest = highest priority)
        activeSources.sort((a, b) => a.priority - b.priority);

        segments.push({
            text: text.slice(start, end),
            charStart: start,
            charEnd: end,
            activeSources,
        });
    }

    return segments;
};

export type ResolvedStyle = {
    css: CSSProperties;
    interactiveSource: ActiveSource | null;
};

export const resolveSegmentStyle = (activeSources: ActiveSource[]): ResolvedStyle => {
    if (activeSources.length === 0) {
        return { css: {}, interactiveSource: null };
    }

    const css: CSSProperties = {};
    let interactiveSource: ActiveSource | null = null;
    const underlines: string[] = [];

    // Highest-priority source (first in sorted array) gets background highlight
    const primary = activeSources[0];
    const primaryColor = primary.sourceKey === "nerResults"
        ? NER_RESULTS_COLOR
        : getEntityGroupColor(primary.label.labelEntityGroup);
    const bgOpacity = primary.style === "bright" ? "33" : "15";
    css.backgroundColor = `${primaryColor}${bgOpacity}`;
    css.borderRadius = "2px";
    css.padding = "1px 0";

    if (primary.interactive) interactiveSource = primary;

    // Lower-priority sources render as underlines
    for (let i = 1; i < activeSources.length; i++) {
        const src = activeSources[i];
        const color = src.sourceKey === "nerResults"
            ? NER_RESULTS_COLOR
            : getEntityGroupColor(src.label.labelEntityGroup);
        if (src.style === "bright") {
            underlines.push(`2px solid ${color}`);
        } else {
            underlines.push(`1px dashed ${color}`);
        }
        if (src.interactive && !interactiveSource) interactiveSource = src;
    }

    // Primary source's own underline/border
    if (primary.style === "bright") {
        underlines.unshift(`2px solid ${primaryColor}`);
    } else {
        underlines.unshift(`1px dashed ${primaryColor}`);
    }

    // Use the first underline as borderBottom (CSS only supports one)
    if (underlines.length > 0) {
        css.borderBottom = underlines[0];
    }

    if (interactiveSource) {
        css.cursor = "pointer";
    }

    return { css, interactiveSource };
};
