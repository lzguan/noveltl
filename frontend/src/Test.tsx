import { rgb } from "./components/labeled-text-lib/builtin/colors";
import { type BoldStyle, type ColorStyle, type ProductStyle, type UnderlineStyle } from "./components/labeled-text-lib/builtin/reducers";
import { type Label } from "./components/labeled-text-lib/core/types";
import { type SegmentManager } from "./components/labeled-text-lib/core/segmentManager";
import { type ManagedLabel } from "./components/labeled-text-lib/react/ManagedLabeledText";
import { DynamicLabeledText, type EditorOverlayRenderContext } from "./components/labeled-text-lib/react/DynamicLabeledText";
import { makePlainBoxRenderer } from "./components/labeled-text-lib/react/Renderer";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type DemoStyle = ProductStyle<[ColorStyle, UnderlineStyle, BoldStyle]>;
type DemoLabel = Label<DemoStyle>;

function toHexColor(color: number): string {
    return `#${color.toString(16).padStart(6, "0")}`;
}

/*
const demoText = "Alice met Bob in Wonderland. The Queen of Hearts watched from afar.";

const demoLabels: DemoLabel[] = [
    {
        range: { start: 0, end: 5 },
        style: [
            { color: rgb(255, 214, 102) },
            { underline: true },
            { bold: false },
        ],
    },
    {
        range: { start: 10, end: 13 },
        style: [
            { color: rgb(130, 170, 255) },
            { underline: false },
            { bold: true },
        ],
    },
    {
        range: { start: 17, end: 27 },
        style: [
            { color: rgb(143, 240, 164) },
            { underline: true },
            { bold: false },
        ],
    },
    {
        range: { start: 17, end: 43 },
        style: [
            { color: rgb(255, 153, 102) },
            { underline: false },
            { bold: true },
        ],
    },
    {
        range: { start: 33, end: 48 },
        style: [
            { color: rgb(255, 102, 178) },
            { underline: true },
            { bold: true },
        ],
    },
    {
        range: { start: 58, end: 62 },
        style: [
            { color: rgb(180, 140, 255) },
            { underline: true },
            { bold: false },
        ],
    },
];

const measuredBoxText =
    "Alice met Bob in Wonderland. The Queen of Hearts watched from afar while Wonderland itself shimmered under layered labels.";

const measuredBoxLabels: DemoLabel[] = [
    {
        range: { start: 0, end: 5 },
        style: [
            { color: rgb(255, 214, 102) },
            { underline: true },
            { bold: false },
        ],
    },
    {
        range: { start: 10, end: 13 },
        style: [
            { color: rgb(130, 170, 255) },
            { underline: false },
            { bold: true },
        ],
    },
    {
        range: { start: 17, end: 27 },
        style: [
            { color: rgb(143, 240, 164) },
            { underline: true },
            { bold: false },
        ],
    },
    {
        range: { start: 17, end: 43 },
        style: [
            { color: rgb(255, 153, 102) },
            { underline: false },
            { bold: true },
        ],
    },
    {
        range: { start: 33, end: 48 },
        style: [
            { color: rgb(255, 102, 178) },
            { underline: true },
            { bold: true },
        ],
    },
    {
        range: { start: 73, end: 106 },
        style: [
            { color: rgb(180, 140, 255) },
            { underline: false },
            { bold: false },
        ],
    },
    {
        range: { start: 73, end: 122 },
        style: [
            { color: rgb(116, 185, 255) },
            { underline: true },
            { bold: false },
        ],
    },
];

const measuredBoxSegmenter = makeBasicSegmenter<DemoStyle, DemoLabel>(1);
const plainSegmenter = makeBasicSegmenter<DemoStyle, DemoLabel>();
const plainTextRenderer = {
    renderText: makePlainTextRenderer<DemoStyle, DemoLabel>(),
};
const measuredBoxRenderer = makePlainBoxRenderer<DemoStyle, DemoLabel>(([colorStyle, underlineStyle, boldStyle]) => ({
        backgroundColor: `${toHexColor(colorStyle.color)}2f`,
        border: `1px solid ${toHexColor(colorStyle.color)}7a`,
        borderRadius: "0.8rem",
        boxShadow: boldStyle.bold
            ? `0 0.35rem 1.35rem ${toHexColor(colorStyle.color)}2e, inset 0 0 0 1px ${toHexColor(colorStyle.color)}1f`
            : `0 0.2rem 0.8rem ${toHexColor(colorStyle.color)}1f, inset 0 0 0 1px ${toHexColor(colorStyle.color)}16`,
        backdropFilter: "blur(8px)",
        outline: underlineStyle.underline ? `2px solid ${toHexColor(colorStyle.color)}28` : undefined,
        outlineOffset: underlineStyle.underline ? "-3px" : undefined,
    }));

function buildStressDemo(blockCount: number): {
    text: string;
    labels: DemoLabel[];
} {
    const baseSentence =
        "Alice met Bob in Wonderland while the Queen of Hearts watched from afar and Wonderland itself shimmered under layered labels. ";
    const labels: DemoLabel[] = [];
    let text = "";

    for (let blockIndex = 0; blockIndex < blockCount; blockIndex += 1) {
        const blockStart = text.length;
        text += baseSentence;

        labels.push({
            range: { start: blockStart, end: blockStart + 5 },
            style: [
                { color: rgb(255, 214, 102) },
                { underline: true },
                { bold: false },
            ],
        });
        labels.push({
            range: { start: blockStart + 10, end: blockStart + 13 },
            style: [
                { color: rgb(130, 170, 255) },
                { underline: false },
                { bold: true },
            ],
        });
        labels.push({
            range: { start: blockStart + 17, end: blockStart + 27 },
            style: [
                { color: rgb(143, 240, 164) },
                { underline: true },
                { bold: false },
            ],
        });
        labels.push({
            range: { start: blockStart + 17, end: blockStart + 63 },
            style: [
                { color: rgb(255, 153, 102) },
                { underline: false },
                { bold: true },
            ],
        });
        labels.push({
            range: { start: blockStart + 38, end: blockStart + 57 },
            style: [
                { color: rgb(255, 102, 178) },
                { underline: true },
                { bold: true },
            ],
        });
        labels.push({
            range: { start: blockStart + 73, end: blockStart + 106 },
            style: [
                { color: rgb(180, 140, 255) },
                { underline: false },
                { bold: false },
            ],
        });
        labels.push({
            range: { start: blockStart + 73, end: blockStart + 120 },
            style: [
                { color: rgb(116, 185, 255) },
                { underline: true },
                { bold: false },
            ],
        });
    }

    return { text, labels };
}

const stressDemo = buildStressDemo(18);

function buildSparseStressDemo(blockCount: number): {
    text: string;
    labels: DemoLabel[];
} {
    const baseSentence =
        "Alice crossed the market square, Bob waited near the old fountain, and the city kept muttering about Wonderland in half-remembered fragments. ";
    const text = baseSentence.repeat(blockCount);
    const labels: DemoLabel[] = [];

    for (let blockIndex = 0; blockIndex < blockCount; blockIndex += 1) {
        const blockStart = blockIndex * baseSentence.length;

        if (blockIndex % 4 === 0) {
            labels.push({
                range: { start: blockStart, end: blockStart + 5 },
                style: [
                    { color: rgb(255, 214, 102) },
                    { underline: true },
                    { bold: false },
                ],
            });
        }

        if (blockIndex % 5 === 2) {
            labels.push({
                range: { start: blockStart + 29, end: blockStart + 32 },
                style: [
                    { color: rgb(130, 170, 255) },
                    { underline: false },
                    { bold: true },
                ],
            });
        }

        if (blockIndex % 6 === 1) {
            labels.push({
                range: { start: blockStart + 88, end: blockStart + 98 },
                style: [
                    { color: rgb(143, 240, 164) },
                    { underline: true },
                    { bold: false },
                ],
            });
        }
    }

    return { text, labels };
}

const sparseStressDemo = buildSparseStressDemo(40);

function collectLabeledTerms(
    text: string,
    entries: {
        term: string;
        style: DemoStyle;
    }[],
): DemoLabel[] {
    const labels: DemoLabel[] = [];

    for (const entry of entries) {
        let searchStart = 0;
        while (searchStart < text.length) {
            const index = text.indexOf(entry.term, searchStart);
            if (index === -1) {
                break;
            }
            labels.push({
                range: { start: index, end: index + entry.term.length },
                style: entry.style,
            });
            searchStart = index + entry.term.length;
        }
    }

    labels.sort((left, right) => left.range.start - right.range.start);
    return labels;
}

function buildChineseChapterDemo(paragraphCount: number): {
    text: string;
    labels: DemoLabel[];
} {
    const paragraph =
        "青云城夜雨未歇，林玄披着旧袍立在长街尽头，望着玄天宗方向翻涌的雷云。苏晚抱剑而来，只说黑风山的妖气又重了三分，陈长青已经先一步入山探路。洛清璃站在酒楼檐下，把镇魂塔的残图递给林玄，提醒他天命玉今夜必有异动。林玄记得三年前也是在青云城，也是苏晚陪他走出城门，而黑风山深处第一次传来镇魂塔的钟鸣。\n";
    const text = paragraph.repeat(paragraphCount);

    const labels = collectLabeledTerms(text, [
        {
            term: "林玄",
            style: [
                { color: rgb(255, 214, 102) },
                { underline: true },
                { bold: true },
            ],
        },
        {
            term: "苏晚",
            style: [
                { color: rgb(130, 170, 255) },
                { underline: false },
                { bold: true },
            ],
        },
        {
            term: "陈长青",
            style: [
                { color: rgb(143, 240, 164) },
                { underline: true },
                { bold: false },
            ],
        },
        {
            term: "洛清璃",
            style: [
                { color: rgb(255, 153, 102) },
                { underline: false },
                { bold: true },
            ],
        },
        {
            term: "玄天宗",
            style: [
                { color: rgb(180, 140, 255) },
                { underline: true },
                { bold: false },
            ],
        },
        {
            term: "黑风山",
            style: [
                { color: rgb(255, 102, 178) },
                { underline: true },
                { bold: true },
            ],
        },
        {
            term: "青云城",
            style: [
                { color: rgb(116, 185, 255) },
                { underline: false },
                { bold: false },
            ],
        },
        {
            term: "镇魂塔",
            style: [
                { color: rgb(255, 183, 77) },
                { underline: true },
                { bold: false },
            ],
        },
        {
            term: "天命玉",
            style: [
                { color: rgb(129, 212, 250) },
                { underline: false },
                { bold: true },
            ],
        },
    ]);

    return { text, labels };
}

const chineseChapterDemo = buildChineseChapterDemo(14);
*/

const measuredBoxRenderer = makePlainBoxRenderer<DemoStyle, DemoLabel>(([colorStyle, underlineStyle, boldStyle]) => ({
    backgroundColor: `${toHexColor(colorStyle.color)}2f`,
    border: `1px solid ${toHexColor(colorStyle.color)}7a`,
    borderRadius: "0.8rem",
    boxShadow: boldStyle.bold
        ? `0 0.35rem 1.35rem ${toHexColor(colorStyle.color)}2e, inset 0 0 0 1px ${toHexColor(colorStyle.color)}1f`
        : `0 0.2rem 0.8rem ${toHexColor(colorStyle.color)}1f, inset 0 0 0 1px ${toHexColor(colorStyle.color)}16`,
    backdropFilter: "blur(8px)",
    outline: underlineStyle.underline ? `2px solid ${toHexColor(colorStyle.color)}28` : undefined,
    outlineOffset: underlineStyle.underline ? "-3px" : undefined,
}));

type EditorMode = "editing" | "labeling";
type DemoLabelData = {
    id: string;
    name: string;
    groupName: string;
    style: DemoStyle;
};
type StoredDemoLabel = {
    id: string;
    labelDataId: string;
    range: { start: number; end: number };
};
type DemoLabelPayload = DemoLabel & {
    labelDataId: string;
    labelName: string;
    groupName: string;
};
type DemoRenderLabel = ManagedLabel<DemoStyle, DemoLabelPayload>;
type TextReplaceOp = {
    id: string;
    type: "replace";
    start: number;
    end: number;
    text: string;
};
type LabelMutationOp = {
    id: string;
    type: "insert" | "remove";
    labelId: string;
    labelDataId: string;
    start: number;
    end: number;
};
type FlushRecord = {
    id: string;
    mode: EditorMode;
    reason: "inactive" | "mode-switch" | "manual";
    summary: string[];
};

const workflowLabelDatas: DemoLabelData[] = [
    {
        id: "alice",
        name: "Alice",
        groupName: "Characters",
        style: [
            { color: rgb(255, 214, 102) },
            { underline: true },
            { bold: true },
        ],
    },
    {
        id: "bob",
        name: "Bob",
        groupName: "Characters",
        style: [
            { color: rgb(130, 170, 255) },
            { underline: false },
            { bold: true },
        ],
    },
    {
        id: "wonderland",
        name: "Wonderland",
        groupName: "Places",
        style: [
            { color: rgb(143, 240, 164) },
            { underline: true },
            { bold: false },
        ],
    },
    {
        id: "queen",
        name: "Queen of Hearts",
        groupName: "Characters",
        style: [
            { color: rgb(255, 102, 178) },
            { underline: true },
            { bold: true },
        ],
    },
];

const workflowInitialText =
    "Alice met Bob in Wonderland. Later, Alice bowed to the Queen of Hearts outside Wonderland.";

const workflowInitialLabels: StoredDemoLabel[] = [
    { id: "wl-1", labelDataId: "alice", range: { start: 0, end: 5 } },
    { id: "wl-2", labelDataId: "bob", range: { start: 10, end: 13 } },
    { id: "wl-3", labelDataId: "wonderland", range: { start: 17, end: 27 } },
    { id: "wl-4", labelDataId: "alice", range: { start: 36, end: 41 } },
    { id: "wl-5", labelDataId: "queen", range: { start: 55, end: 70 } },
    { id: "wl-6", labelDataId: "wonderland", range: { start: 79, end: 89 } },
];

function DemoEditorOverlay({
    state,
    resolveSelectionRects,
}: EditorOverlayRenderContext<DemoStyle, DemoRenderLabel>) {
    const selection = state.highlight ?? state.cursor;
    if (!selection) {
        return null;
    }

    const rects = resolveSelectionRects(selection);
    if (rects.length === 0) {
        return null;
    }

    const isCollapsed = selection.anchor === selection.focus;

    return (
        <>
            {rects.map((rect, index) => (
                <div
                    key={`${selection.anchor}:${selection.focus}:${index}`}
                    style={isCollapsed
                        ? {
                            position: "absolute",
                            left: rect.left,
                            top: rect.top,
                            width: "2px",
                            height: rect.height,
                            borderRadius: "999px",
                            background: "#0f172a",
                            boxShadow: "0 0 0 1px rgba(255,255,255,0.4)",
                        }
                        : {
                            position: "absolute",
                            left: rect.left,
                            top: rect.top,
                            width: rect.width,
                            height: rect.height,
                            borderRadius: "0.35rem",
                            background: "rgba(59, 130, 246, 0.22)",
                            outline: "1px solid rgba(59, 130, 246, 0.22)",
                        }}
                />
            ))}
        </>
    );
}

function findTextReplacement(prev: string, next: string): TextReplaceOp | null {
    if (prev === next) {
        return null;
    }

    let start = 0;
    while (start < prev.length && start < next.length && prev[start] === next[start]) {
        start += 1;
    }

    let prevEnd = prev.length;
    let nextEnd = next.length;
    while (prevEnd > start && nextEnd > start && prev[prevEnd - 1] === next[nextEnd - 1]) {
        prevEnd -= 1;
        nextEnd -= 1;
    }

    return {
        id: `text-op-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "replace",
        start,
        end: prevEnd,
        text: next.slice(start, nextEnd),
    };
}

function overlaps(left: { start: number; end: number }, right: { start: number; end: number }) {
    return left.start < right.end && right.start < left.end;
}

function buildRenderLabels(
    labelDatas: DemoLabelData[],
    labels: StoredDemoLabel[],
): DemoRenderLabel[] {
    const dataById = new Map(labelDatas.map((labelData) => [labelData.id, labelData]));

    return labels.flatMap((label) => {
        const labelData = dataById.get(label.labelDataId);
        if (!labelData) {
            return [];
        }
        return [{
            id: label.id,
            labelDataId: label.labelDataId,
            labelName: labelData.name,
            groupName: labelData.groupName,
            range: label.range,
            style: labelData.style,
        }];
    });
}

function BasicWorkflowManagerDemo() {
    const [mode, setMode] = useState<EditorMode>("editing");
    const [text, setText] = useState(workflowInitialText);
    const [labels, setLabels] = useState<StoredDemoLabel[]>(workflowInitialLabels);
    const [editingOps, setEditingOps] = useState<TextReplaceOp[]>([]);
    const [labelingOps, setLabelingOps] = useState<LabelMutationOp[]>([]);
    const [flushes, setFlushes] = useState<FlushRecord[]>([]);
    const [validationMessage, setValidationMessage] = useState<string | null>(null);
    const [inspectPopup, setInspectPopup] = useState<{
        pos: number;
        labelIds: string[];
        index: number;
    } | null>(null);
    const [insertPopup, setInsertPopup] = useState<{
        start: number;
        end: number;
        labelDataId: string;
    } | null>(null);

    const dragSelectionRef = useRef<{ anchor: number; focus: number } | null>(null);
    const labelIdCounterRef = useRef(100);
    const dynamicManagerRef = useRef<SegmentManager<DemoStyle, DemoLabelPayload> | null>(null);
    const textRef = useRef(text);
    const labelsRef = useRef(labels);
    const labelDataById = useMemo(
        () => new Map(workflowLabelDatas.map((labelData) => [labelData.id, labelData])),
        [],
    );

    const syncFromManager = useCallback((manager: SegmentManager<DemoStyle, DemoLabelPayload>) => {
        const nextText = manager.getText();
        const nextLabels = manager
            .getSegments()
            .flatMap((segment) =>
                segment.labels.map((label) => ({
                    id: label.id,
                    labelDataId: label.labelDataId,
                    range: {
                        start: segment.start + label.interval.start,
                        end: segment.start + label.interval.end,
                    },
                })),
            )
            .sort((left, right) => left.range.start - right.range.start);

        const sameText = textRef.current === nextText;
        const sameLabels = labelsRef.current.length === nextLabels.length
            && labelsRef.current.every((label, index) => (
                label.id === nextLabels[index].id
                && label.labelDataId === nextLabels[index].labelDataId
                && label.range.start === nextLabels[index].range.start
                && label.range.end === nextLabels[index].range.end
            ));

        if (sameText && sameLabels) {
            return;
        }

        textRef.current = nextText;
        labelsRef.current = nextLabels;
        setText(nextText);
        setLabels(nextLabels);
    }, []);

    useEffect(() => {
        textRef.current = text;
    }, [text]);

    useEffect(() => {
        labelsRef.current = labels;
    }, [labels]);

    const flushQueue = useCallback((targetMode: EditorMode, reason: "inactive" | "mode-switch" | "manual") => {
        if (targetMode === "editing") {
            if (editingOps.length === 0) {
                return;
            }
            setFlushes((prev) => [
                {
                    id: `flush-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                    mode: "editing",
                    reason,
                    summary: editingOps.map((op) => `replace [${op.start}, ${op.end}) with "${op.text}"`),
                },
                ...prev,
            ]);
            setEditingOps([]);
            return;
        }
        if (labelingOps.length === 0) {
            return;
        }
        setFlushes((prev) => [
            {
                id: `flush-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                mode: "labeling",
                reason,
                summary: labelingOps.map((op) => `${op.type} ${op.labelDataId} @ [${op.start}, ${op.end})`),
            },
            ...prev,
        ]);
        setLabelingOps([]);
    }, [editingOps, labelingOps]);

    const flushAllQueues = useCallback((reason: "manual" | "mode-switch") => {
        flushQueue("editing", reason);
        flushQueue("labeling", reason);
    }, [flushQueue]);

    useEffect(() => {
        if (editingOps.length === 0) {
            return;
        }
        const timeoutId = window.setTimeout(() => {
            flushQueue("editing", "inactive");
        }, 1600);
        return () => window.clearTimeout(timeoutId);
    }, [editingOps, flushQueue]);

    useEffect(() => {
        if (labelingOps.length === 0) {
            return;
        }
        const timeoutId = window.setTimeout(() => {
            flushQueue("labeling", "inactive");
        }, 1600);
        return () => window.clearTimeout(timeoutId);
    }, [flushQueue, labelingOps]);

    const switchMode = (nextMode: EditorMode) => {
        if (nextMode === mode) {
            return;
        }
        flushQueue(mode, "mode-switch");
        setMode(nextMode);
        setInspectPopup(null);
        setInsertPopup(null);
        setValidationMessage(null);
    };

    const canInsertLabel = (labelDataId: string, start: number, end: number) => {
        return !labels.some((label) => (
            label.labelDataId === labelDataId &&
            overlaps(label.range, { start, end })
        ));
    };

    const selectedInspectLabel = inspectPopup
        ? labels.find((label) => label.id === inspectPopup.labelIds[inspectPopup.index])
        : null;
    const selectedInspectLabelData = selectedInspectLabel
        ? labelDataById.get(selectedInspectLabel.labelDataId)
        : null;

    const insertLabel = () => {
        if (!insertPopup) {
            return;
        }
        if (insertPopup.start === insertPopup.end) {
            setValidationMessage("Pick a non-empty range before inserting a label.");
            return;
        }
        if (!canInsertLabel(insertPopup.labelDataId, insertPopup.start, insertPopup.end)) {
            setValidationMessage("Labels from the same label data cannot overlap.");
            return;
        }

        const manager = dynamicManagerRef.current;
        const labelData = labelDataById.get(insertPopup.labelDataId);
        if (!manager || !labelData) {
            return;
        }

        const newLabel: DemoRenderLabel = {
            id: `wl-${labelIdCounterRef.current + 1}`,
            labelDataId: labelData.id,
            labelName: labelData.name,
            groupName: labelData.groupName,
            interval: {
                start: insertPopup.start,
                end: insertPopup.end,
            },
            style: labelData.style,
        };

        manager.addLabel(`wl-${labelIdCounterRef.current++}`, newLabel);
        syncFromManager(manager);
        setLabelingOps((prev) => [...prev, {
            id: `label-op-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            type: "insert",
            labelId: newLabel.id,
            labelDataId: newLabel.labelDataId,
            start: insertPopup.start,
            end: insertPopup.end,
        }]);
        setInsertPopup(null);
        setValidationMessage(null);
    };

    const removeSelectedLabel = () => {
        if (!selectedInspectLabel) {
            return;
        }
        const manager = dynamicManagerRef.current;
        if (!manager) {
            return;
        }
        manager.removeLabel(selectedInspectLabel.id);
        syncFromManager(manager);
        setLabelingOps((prev) => [...prev, {
            id: `label-op-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            type: "remove",
            labelId: selectedInspectLabel.id,
            labelDataId: selectedInspectLabel.labelDataId,
            start: selectedInspectLabel.range.start,
            end: selectedInspectLabel.range.end,
        }]);
        setInspectPopup(null);
        setValidationMessage(null);
    };

    const handleDynamicReady = useCallback((manager: SegmentManager<DemoStyle, DemoLabelPayload>) => {
        dynamicManagerRef.current = manager;
        syncFromManager(manager);
    }, [syncFromManager]);

    return (
        <section
            style={{
                marginTop: "2rem",
                border: "1px solid #d7e4ea",
                borderRadius: "1.25rem",
                background:
                    "linear-gradient(180deg, rgba(248,252,252,0.98) 0%, rgba(238,247,247,0.98) 100%)",
                padding: "1.25rem",
                boxShadow: "0 1.25rem 3rem rgba(15, 23, 42, 0.08)",
            }}
        >
            <h2 style={{ marginTop: 0 }}>Basic Workflow Manager Demo</h2>
            <p style={{ color: "#52606d" }}>
                This is a local-only manager for the first three workflow requirements:
                two modes, separate op buffers with inactivity flush, direct text editing in
                the labeled surface, and click/selection label flows in labeling mode.
            </p>
            <div
                style={{
                    display: "flex",
                    gap: "0.75rem",
                    flexWrap: "wrap",
                    marginBottom: "1rem",
                }}
            >
                <button type="button" onClick={() => switchMode("editing")} disabled={mode === "editing"}>
                    Editing Mode
                </button>
                <button type="button" onClick={() => switchMode("labeling")} disabled={mode === "labeling"}>
                    Labeling Mode
                </button>
                <button
                    type="button"
                    onClick={() => flushQueue(mode, "manual")}
                    disabled={mode === "editing" ? editingOps.length === 0 : labelingOps.length === 0}
                >
                    Flush Current Queue
                </button>
                <button
                    type="button"
                    onClick={() => flushAllQueues("manual")}
                    disabled={editingOps.length === 0 && labelingOps.length === 0}
                >
                    Flush All Queues
                </button>
                <div style={{ paddingTop: "0.4rem", color: "#52606d" }}>
                    Pending ops: editing <code>{editingOps.length}</code>, labeling <code>{labelingOps.length}</code>
                </div>
            </div>

            {validationMessage ? (
                <div
                    style={{
                        marginBottom: "1rem",
                        padding: "0.75rem 0.9rem",
                        borderRadius: "0.85rem",
                        background: "rgba(254, 240, 138, 0.35)",
                        border: "1px solid rgba(202, 138, 4, 0.22)",
                        color: "#854d0e",
                    }}
                >
                    {validationMessage}
                </div>
            ) : null}

            <div
                style={{
                    position: "relative",
                    border: "1px solid rgba(148, 163, 184, 0.28)",
                    borderRadius: "1rem",
                    padding: "1rem",
                    background:
                        "linear-gradient(180deg, rgba(255,255,255,0.88) 0%, rgba(246,250,252,0.92) 100%)",
                    boxShadow:
                        "inset 0 1px 0 rgba(255,255,255,0.85), 0 0.65rem 1.8rem rgba(15, 23, 42, 0.06)",
                }}
            >
                <DynamicLabeledText
                    initialText={workflowInitialText}
                    initialLabels={buildRenderLabels(workflowLabelDatas, workflowInitialLabels)}
                    gap={1}
                    editable={mode === "editing"}
                    render={measuredBoxRenderer}
                    containerStyle={{
                        isolation: "isolate",
                        minHeight: "8rem",
                        fontFamily: "Georgia, 'Times New Roman', serif",
                        lineHeight: 1.7,
                    }}
                    onReady={handleDynamicReady}
                    callbacks={{
                        onInput: () => {
                            const manager = dynamicManagerRef.current;
                            if (!manager) {
                                return;
                            }
                            const nextText = manager.getText();
                            const op = findTextReplacement(textRef.current, nextText);
                            const nextLabels = manager
                                .getSegments()
                                .flatMap((segment) =>
                                    segment.labels.map((label) => ({
                                        id: label.id,
                                        labelDataId: label.labelDataId,
                                        range: {
                                            start: segment.start + label.interval.start,
                                            end: segment.start + label.interval.end,
                                        },
                                    })),
                                )
                                .sort((left, right) => left.range.start - right.range.start);
                            const nextLabelIds = new Set(nextLabels.map((label) => label.id));
                            const removedLabelIds = labelsRef.current
                                .filter((label) => !nextLabelIds.has(label.id))
                                .map((label) => label.id);

                            syncFromManager(manager);
                            if (op) {
                                setEditingOps((prev) => [...prev, op]);
                            }
                            setInspectPopup(null);
                            setInsertPopup(null);
                            setValidationMessage(removedLabelIds.length > 0
                                ? `Removed ${removedLabelIds.length} label(s) that intersected the edit.`
                                : null);
                        },
                        onPointerDown: ({ pos, controller }) => {
                            if (mode !== "labeling") {
                                return;
                            }
                            dragSelectionRef.current = { anchor: pos, focus: pos };
                            controller.setCursor({ anchor: pos, focus: pos });
                            controller.setHighlight({ anchor: pos, focus: pos });
                            setInspectPopup(null);
                            setInsertPopup(null);
                            setValidationMessage(null);
                        },
                        onPointerMove: ({ event, pos, controller }) => {
                            if (mode !== "labeling") {
                                return;
                            }
                            if (event.buttons === 0 || !dragSelectionRef.current) {
                                return;
                            }
                            dragSelectionRef.current = {
                                anchor: dragSelectionRef.current.anchor,
                                focus: pos,
                            };
                            controller.setCursor(dragSelectionRef.current);
                            controller.setHighlight(dragSelectionRef.current);
                        },
                        onPointerUp: ({ pos, activeLabelIds, controller }) => {
                            if (mode !== "labeling") {
                                return;
                            }
                            const currentSelection = dragSelectionRef.current ?? { anchor: pos, focus: pos };
                            const finalSelection = { anchor: currentSelection.anchor, focus: pos };
                            dragSelectionRef.current = null;
                            controller.setCursor(finalSelection);
                            controller.setHighlight(finalSelection);

                            const start = Math.min(finalSelection.anchor, finalSelection.focus);
                            const end = Math.max(finalSelection.anchor, finalSelection.focus);

                            if (start !== end) {
                                setInsertPopup({
                                    start,
                                    end,
                                    labelDataId: workflowLabelDatas[0].id,
                                });
                                setInspectPopup(null);
                                return;
                            }

                            if (activeLabelIds.length > 0) {
                                setInspectPopup({
                                    pos,
                                    labelIds: activeLabelIds,
                                    index: 0,
                                });
                                setInsertPopup(null);
                            }
                        },
                    }}
                    renderEditorOverlay={DemoEditorOverlay}
                />

                {inspectPopup && selectedInspectLabel && selectedInspectLabelData ? (
                    <div
                        style={{
                            marginTop: "1rem",
                            padding: "0.9rem 1rem",
                            borderRadius: "0.9rem",
                            border: "1px solid rgba(148, 163, 184, 0.28)",
                            background: "rgba(255,255,255,0.95)",
                            boxShadow: "0 0.9rem 2rem rgba(15, 23, 42, 0.08)",
                        }}
                    >
                        <div style={{ marginBottom: "0.5rem", color: "#52606d" }}>
                            Labels at position <code>{inspectPopup.pos}</code>
                        </div>
                        <strong>{selectedInspectLabelData.name}</strong>
                        <div style={{ color: "#52606d", marginTop: "0.25rem" }}>
                            Group: {selectedInspectLabelData.groupName} · Range{" "}
                            <code>[{selectedInspectLabel.range.start}, {selectedInspectLabel.range.end})</code>
                        </div>
                        <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
                            <button
                                type="button"
                                onClick={() => setInspectPopup((prev) => (
                                    prev
                                        ? { ...prev, index: (prev.index - 1 + prev.labelIds.length) % prev.labelIds.length }
                                        : prev
                                ))}
                                disabled={inspectPopup.labelIds.length <= 1}
                            >
                                Previous
                            </button>
                            <button
                                type="button"
                                onClick={() => setInspectPopup((prev) => (
                                    prev
                                        ? { ...prev, index: (prev.index + 1) % prev.labelIds.length }
                                        : prev
                                ))}
                                disabled={inspectPopup.labelIds.length <= 1}
                            >
                                Next
                            </button>
                            <button type="button" onClick={removeSelectedLabel}>
                                Remove Label
                            </button>
                        </div>
                    </div>
                ) : null}

                {insertPopup ? (
                    <div
                        style={{
                            marginTop: "1rem",
                            padding: "0.9rem 1rem",
                            borderRadius: "0.9rem",
                            border: "1px solid rgba(148, 163, 184, 0.28)",
                            background: "rgba(255,255,255,0.95)",
                            boxShadow: "0 0.9rem 2rem rgba(15, 23, 42, 0.08)",
                        }}
                    >
                        <div style={{ marginBottom: "0.5rem", color: "#52606d" }}>
                            Insert label for <code>[{insertPopup.start}, {insertPopup.end})</code>
                        </div>
                        <select
                            value={insertPopup.labelDataId}
                            onChange={(event) => setInsertPopup((prev) => (
                                prev
                                    ? { ...prev, labelDataId: event.target.value }
                                    : prev
                            ))}
                            style={{
                                width: "100%",
                                marginBottom: "0.75rem",
                                padding: "0.65rem 0.75rem",
                                borderRadius: "0.75rem",
                                border: "1px solid rgba(148, 163, 184, 0.35)",
                            }}
                        >
                            {workflowLabelDatas.map((labelData) => (
                                <option key={labelData.id} value={labelData.id}>
                                    {labelData.groupName} · {labelData.name}
                                </option>
                            ))}
                        </select>
                        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                            <button type="button" onClick={insertLabel}>
                                Insert Label
                            </button>
                            <button type="button" onClick={() => setInsertPopup(null)}>
                                Cancel
                            </button>
                        </div>
                    </div>
                ) : null}
            </div>

            <div
                style={{
                    marginTop: "1rem",
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))",
                    gap: "0.9rem",
                }}
            >
                <div
                    style={{
                        padding: "0.9rem 1rem",
                        borderRadius: "0.9rem",
                        background: "rgba(255,255,255,0.7)",
                        border: "1px solid rgba(148, 163, 184, 0.18)",
                    }}
                >
                    <strong>Label Data</strong>
                    <div style={{ marginTop: "0.65rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {workflowLabelDatas.map((labelData) => (
                            <div key={labelData.id}>
                                <code>{labelData.groupName}</code> · {labelData.name}
                            </div>
                        ))}
                    </div>
                </div>
                <div
                    style={{
                        padding: "0.9rem 1rem",
                        borderRadius: "0.9rem",
                        background: "rgba(255,255,255,0.7)",
                        border: "1px solid rgba(148, 163, 184, 0.18)",
                    }}
                >
                    <strong>Flushed Queues</strong>
                    <div style={{ marginTop: "0.65rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        {flushes.length === 0 ? (
                            <div style={{ color: "#64748b" }}>No flushes yet.</div>
                        ) : flushes.map((flush) => (
                            <div key={flush.id}>
                                <div>
                                    <code>{flush.mode}</code> · {flush.reason}
                                </div>
                                <div style={{ color: "#64748b", fontSize: "0.92rem" }}>
                                    {flush.summary.join(" | ")}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}

/*
const managedDemoText = "Alice met Bob in Wonderland.";
const managedDemoLabels: ManagedDemoLabel[] = [
    {
        id: "1",
        range: { start: 0, end: 5 },
        style: [
            { color: rgb(255, 214, 102) },
            { underline: true },
            { bold: false },
        ],
    },
    {
        id: "2",
        range: { start: 10, end: 13 },
        style: [
            { color: rgb(130, 170, 255) },
            { underline: false },
            { bold: true },
        ],
    },
    {
        id: "3",
        range: { start: 17, end: 27 },
        style: [
            { color: rgb(143, 240, 164) },
            { underline: true },
            { bold: false },
        ],
    },
];

function ManagedLabeledTextDemo() {
    const [manager, setManager] = useState<SegmentManager<DemoStyle, DemoLabel> | null>(null);

    return (
        <div
            style={{
                border: "1px solid #d7e4ea",
                borderRadius: "1.25rem",
                background:
                    "linear-gradient(180deg, rgba(248,252,252,0.98) 0%, rgba(238,247,247,0.98) 100%)",
                padding: "1.25rem",
                boxShadow: "0 1.25rem 3rem rgba(15, 23, 42, 0.08)",
            }}
        >
            <div
                style={{
                    display: "flex",
                    gap: "0.75rem",
                    flexWrap: "wrap",
                    marginBottom: "1rem",
                }}
            >
                <button
                    type="button"
                    onClick={() => manager?.insertTextAt(6, "quietly ")}
                    disabled={!manager}
                >
                    Insert `quietly `
                </button>
                <button
                    type="button"
                    onClick={() => manager?.deleteTextAt(6, 8)}
                    disabled={!manager}
                >
                    Delete 8 chars at 6
                </button>
            </div>
            <div
                style={{
                    border: "1px solid rgba(148, 163, 184, 0.28)",
                    borderRadius: "1rem",
                    padding: "1.15rem 1.2rem 1.25rem",
                    background:
                        "linear-gradient(180deg, rgba(255,255,255,0.88) 0%, rgba(246,250,252,0.92) 100%)",
                    boxShadow:
                        "inset 0 1px 0 rgba(255,255,255,0.85), 0 0.65rem 1.8rem rgba(15, 23, 42, 0.06)",
                }}
            >
                <ManagedLabeledText
                    initialText={managedDemoText}
                    initialLabels={managedDemoLabels}
                    gap={1}
                    render={measuredBoxRenderer}
                    containerStyle={measuredBoxLayering.containerStyle}
                    overlayStyle={measuredBoxLayering.overlayStyle}
                    onReady={setManager}
                />
            </div>
        </div>
    );
}
*/

function Test() {
    return (
        <main
            style={{
                padding: "2.5rem 2rem 4rem",
                maxWidth: "58rem",
                margin: "0 auto",
                color: "#1f2937",
            }}
        >
            <h1>Labeled Text Dynamic Demo</h1>
            <p>
                This page is now focused on the dynamic editor prototype: one labeled
                surface, editing and labeling modes, local op queues, and label-aware
                interactions.
            </p>
            <BasicWorkflowManagerDemo />
        </main>
    );
}

export { Test };
