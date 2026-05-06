import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
    type JSX,
    type RefObject,
} from "react";
import { useParams, useSearchParams } from "react-router-dom";

import {
    createChapterNovelsNovelIdChaptersPost,
    readChaptersByNovelChaptersGet,
    readEditChapterDataEditChapterDataChapterIdGet,
    readNovelNovelsNovelIdGet,
    type Chapter,
    type DetailHttpErrorResponse,
    type EditChapterData,
    type Label,
    type Novel,
    type RequestConflictErrorResponse,
    type Role,
} from "@/client";
import { toHex } from "@/components/labeled-text-lib/builtin/colors";
import { DynamicLabeledText, type Caret as EditorCaret } from "@/components/labeled-text-lib/react/DynamicLabeledText";
import { makePlainBoxRenderer } from "@/components/labeled-text-lib/react/Renderer";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label as FieldLabel } from "@/components/ui/label";
import { useLoader } from "@/lib/utils";
import { extractParams } from "@/routes";

import { useController } from "./controller/controller";
import type { MyStyle, ProvisionalId, UserEvent } from "./controller/types";
import { buildRuntime } from "./controller/utils";

type WorkspaceMode = "edit" | "label" | "view";

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

type WorkspaceProps = {
    editChapterData: EditChapterData;
    novel: Novel;
    chapterList: Chapter[];
    chapterDraftNum: string;
    chapterDraftTitle: string;
    chapterDraftIsPublic: boolean;
    createChapterError: string | null;
    isCreatingChapter: boolean;
    onChapterDraftNumChange: (value: string) => void;
    onChapterDraftTitleChange: (value: string) => void;
    onChapterDraftVisibilityChange: (value: boolean) => void;
    onCreateChapter: () => Promise<void>;
    onReloadChapterData: () => Promise<EditChapterData | null>;
    onSelectChapter: (chapterId: string) => void;
};

function clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(value, max));
}

function getSuggestedChapterNumber(chapters: Chapter[]): number {
    if (chapters.length === 0) {
        return 1;
    }
    return Math.max(...chapters.map((chapter) => chapter.chapterNum)) + 1;
}

function normalizeSelection(caret: EditorCaret): { start: number; end: number } {
    return {
        start: Math.min(caret.anchor, caret.focus),
        end: Math.max(caret.anchor, caret.focus),
    };
}

function selectionText(text: string, caret: EditorCaret): string {
    const { start, end } = normalizeSelection(caret);
    return text.slice(start, end);
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

function resolvePointerPosition(
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

function isWordBoundaryCharacter(value: string | undefined): boolean {
    if (!value) {
        return true;
    }
    return /[\s.,;:!?()[\]{}"'`~\-–—/\\<>|@#$%^&*_+=，。！？；：、（）【】《》「」『』]/u.test(value);
}

function findWordBounds(text: string, pos: number): { start: number; end: number } {
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

function measureSelectionRects(
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

    const segmentElements = Array.from(container.querySelectorAll<HTMLElement>("[data-segment-start]"));
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
            rects.push(...clientRects.map((rect) => ({
                left: rect.left - overlayRect.left,
                top: rect.top - overlayRect.top,
                width: rect.width,
                height: rect.height,
            })));
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

    const endSegment = text.length === 0 ? null : getSegmentElementByStart(containerRef, text.length - 1);
    if (!endSegment) {
        return [];
    }
    const fallbackRect = endSegment.getBoundingClientRect();
    return [{
        left: fallbackRect.right - overlayRect.left,
        top: fallbackRect.top - overlayRect.top,
        width: 0,
        height: fallbackRect.height,
    }];
}

function isDetailHttpErrorResponse(error: unknown): error is DetailHttpErrorResponse {
    return typeof error === "object" && error !== null && typeof (error as { detail?: unknown }).detail === "string";
}

function isRequestConflictErrorResponse(error: unknown): error is RequestConflictErrorResponse {
    if (typeof error !== "object" || error === null) {
        return false;
    }
    const detail = (error as { detail?: unknown }).detail;
    return (
        typeof detail === "object"
        && detail !== null
        && typeof (detail as { detail?: unknown }).detail === "string"
        && typeof (detail as { cacheConflict?: unknown }).cacheConflict === "boolean"
    );
}

function formatUnknownError(error: unknown): string {
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

function extractErrorMessages(errors: Error[] | null): string[] {
    if (!errors) {
        return [];
    }
    return errors.map((error) => error.message);
}

function isOutdatedError(error: Error): boolean {
    return error.message.toLowerCase().includes("outdated");
}

async function loadNovel(novelId: string): Promise<Novel> {
    const response = await readNovelNovelsNovelIdGet({
        path: { novelId },
    });
    if (!response.data) {
        throw response.error ?? new Error("Failed to load novel.");
    }
    return response.data;
}

async function loadChapters(novelId: string): Promise<Chapter[]> {
    const response = await readChaptersByNovelChaptersGet({
        query: { novelId },
    });
    if (!response.data) {
        throw response.error ?? new Error("Failed to load chapter list.");
    }
    return response.data;
}

async function loadEditChapterData(chapterId: string, novelId: string, labelGroupsNum: number): Promise<EditChapterData> {
    const response = await readEditChapterDataEditChapterDataChapterIdGet({
        path: { chapterId },
        query: {
            novelId,
            labelGroupsNum,
        },
    });
    if (!response.data) {
        throw response.error ?? new Error("Failed to load chapter editor data.");
    }
    return response.data;
}

function LabelStateBadge({ label }: { label: Label }) {
    return (
        <span className="rounded-full border border-black/10 bg-black/5 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-black/55">
            {label.labelDirty ? "Dirty" : "Clean"}
        </span>
    );
}

function StatusPill({
    tone,
    children,
}: {
    tone: "default" | "warning" | "success";
    children: string;
}) {
    const tones = {
        default: "border-black/10 bg-white/80 text-black/60",
        warning: "border-amber-300 bg-amber-50 text-amber-900",
        success: "border-emerald-300 bg-emerald-50 text-emerald-800",
    } as const;

    return (
        <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] ${tones[tone]}`}>
            {children}
        </span>
    );
}

function RoleTone({ role }: { role: Role }) {
    const tone = role === "owner"
        ? "border-orange-300 bg-orange-50 text-orange-900"
        : role === "editor"
            ? "border-sky-300 bg-sky-50 text-sky-900"
            : "border-slate-300 bg-slate-100 text-slate-700";

    return (
        <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] ${tone}`}>
            {role}
        </span>
    );
}

type CreateChapterPanelProps = {
    chapterDraftNum: string;
    chapterDraftTitle: string;
    chapterDraftIsPublic: boolean;
    createChapterError: string | null;
    isCreatingChapter: boolean;
    disableCreation?: boolean;
    onChapterDraftNumChange: (value: string) => void;
    onChapterDraftTitleChange: (value: string) => void;
    onChapterDraftVisibilityChange: (value: boolean) => void;
    onCreateChapter: () => Promise<void>;
};

function CreateChapterPanel({
    chapterDraftNum,
    chapterDraftTitle,
    chapterDraftIsPublic,
    createChapterError,
    isCreatingChapter,
    disableCreation = false,
    onChapterDraftNumChange,
    onChapterDraftTitleChange,
    onChapterDraftVisibilityChange,
    onCreateChapter,
}: CreateChapterPanelProps) {
    const isSubmitDisabled = disableCreation || isCreatingChapter || chapterDraftNum.trim().length === 0;

    return (
        <div className="space-y-4 rounded-[1.6rem] border border-black/8 bg-[linear-gradient(180deg,_rgba(255,255,255,0.94),_rgba(248,244,236,0.88))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)]">
            <div className="space-y-1">
                <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">New chapter</div>
                <p className="text-sm text-slate-600">
                    Add the next chapter without leaving the editor workspace.
                </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-[120px_minmax(0,1fr)]">
                <div className="space-y-2">
                    <FieldLabel htmlFor="chapter-num">Number</FieldLabel>
                    <Input
                        id="chapter-num"
                        inputMode="numeric"
                        value={chapterDraftNum}
                        onChange={(event) => onChapterDraftNumChange(event.target.value)}
                        disabled={disableCreation}
                    />
                </div>
                <div className="space-y-2">
                    <FieldLabel htmlFor="chapter-title">Title</FieldLabel>
                    <Input
                        id="chapter-title"
                        value={chapterDraftTitle}
                        onChange={(event) => onChapterDraftTitleChange(event.target.value)}
                        placeholder="New chapter title"
                        disabled={disableCreation}
                    />
                </div>
            </div>

            <label className="flex items-center gap-3 rounded-xl border border-black/8 bg-white/80 px-3 py-2 text-sm text-slate-700">
                <input
                    type="checkbox"
                    checked={chapterDraftIsPublic}
                    onChange={(event) => onChapterDraftVisibilityChange(event.target.checked)}
                    disabled={disableCreation}
                    className="h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-500"
                />
                Make this chapter public
            </label>

            {createChapterError ? (
                <div className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
                    {createChapterError}
                </div>
            ) : null}

            <Button
                type="button"
                className="w-full"
                onClick={() => void onCreateChapter()}
                disabled={isSubmitDisabled}
            >
                {isCreatingChapter ? "Creating Chapter..." : "Create Chapter"}
            </Button>
        </div>
    );
}

function EditNovelWorkspace({
    editChapterData,
    novel,
    chapterList,
    chapterDraftNum,
    chapterDraftTitle,
    chapterDraftIsPublic,
    createChapterError,
    isCreatingChapter,
    onChapterDraftNumChange,
    onChapterDraftTitleChange,
    onChapterDraftVisibilityChange,
    onCreateChapter,
    onReloadChapterData,
    onSelectChapter,
}: WorkspaceProps) {
    const [mode, setMode] = useState<WorkspaceMode>("view");
    const [errors, setErrors] = useState<Error[] | null>(null);
    const [caret, setCaret] = useState<EditorCaret>({ anchor: 0, focus: 0, visible: false });
    const [editorActive, setEditorActive] = useState(false);
    const [activeGroupId, setActiveGroupId] = useState<ProvisionalId | null>(null);
    const [selectedLabelId, setSelectedLabelId] = useState<ProvisionalId | null>(null);
    const [newGroupName, setNewGroupName] = useState("");
    const [, setSurfaceVersion] = useState(0);
    const [isSyncing, setIsSyncing] = useState(false);
    const dragAnchorRef = useRef<number | null>(null);
    const modeRef = useRef<WorkspaceMode>(mode);

    useEffect(() => {
        modeRef.current = mode;
    }, [mode]);

    const getMode = useCallback(() => modeRef.current, []);

    const runtime = useMemo(
        () => buildRuntime(
            setErrors,
            { novelId: novel.novelId },
            { chapterId: editChapterData.chapter.chapterId },
            editChapterData,
        ),
        [editChapterData, novel.novelId],
    );

    const controller = useController(
        editChapterData,
        getMode,
        setMode,
        runtime,
        setErrors,
    );

    const [textSnapshot, setTextSnapshot] = useState(() => runtime.uiManager.getText());

    useEffect(() => runtime.uiManager.subscribe(() => {
        setTextSnapshot(runtime.uiManager.getText());
        setSurfaceVersion((previous) => previous + 1);
    }), [runtime]);

    useEffect(() => {
        runtime.requestManager.attachControllerSignalHandler(controller.handleSignal);
        if (!runtime.requestManager.isQueueEmpty()) {
            void runtime.requestManager.start();
        }
    }, [controller.handleSignal, runtime]);

    useEffect(() => {
        const syncInterval = window.setInterval(() => {
            const nextSyncing = !runtime.requestManager.isQueueEmpty();
            setIsSyncing((previous) => {
                if (previous !== nextSyncing) {
                    setSurfaceVersion((current) => current + 1);
                }
                return nextSyncing;
            });
        }, 250);
        return () => {
            window.clearInterval(syncInterval);
        };
    }, [runtime]);

    const entries = runtime.dataManager.getEntries();
    const activeEntry = entries.find((entry) => entry.labelGroup.labelGroupId === activeGroupId) ?? null;
    const selectedLabel = activeEntry?.labels.find((label) => label.labelId === selectedLabelId) ?? null;
    const selection = normalizeSelection(caret);
    const selectedText = selectionText(textSnapshot, caret);

    const renderCaret = useCallback(
        ({
            caret: currentCaret,
            containerRef,
            overlayRef,
        }: {
            caret: EditorCaret;
            containerRef: RefObject<HTMLDivElement | null>;
            overlayRef: RefObject<HTMLDivElement | null>;
        }): JSX.Element => {
            const rects = measureSelectionRects(textSnapshot, currentCaret, containerRef, overlayRef);
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
                            height: Math.max(rect.height, 18),
                            background: "#111827",
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
                                background: "rgba(242, 161, 75, 0.25)",
                                borderRadius: 6,
                            }}
                        />
                    ))}
                </>
            );
        },
        [textSnapshot],
    );

    const renderer = useMemo(() => ({
        ...makePlainBoxRenderer<MyStyle, StyledLabel<MyStyle>>((style) => {
            const [colorStyle, metaStyle] = style;
            const baseColor = toHex(colorStyle.color);
            const borderStyle = metaStyle.mutable ? "solid" : "dashed";
            const opacity = metaStyle.visible ? 1 : 0.25;
            const boxShadow = metaStyle.cursorStatus === "clicked"
                ? "0 0 0 2px rgba(17, 24, 39, 0.35)"
                : metaStyle.cursorStatus === "hovered"
                    ? "0 0 0 2px rgba(242, 161, 75, 0.35)"
                    : metaStyle.active
                        ? "0 0 0 2px rgba(17, 24, 39, 0.16)"
                        : "none";

            return {
                backgroundColor: `${baseColor}2d`,
                border: `1px ${borderStyle} ${baseColor}`,
                borderRadius: "0.5rem",
                boxShadow,
                opacity,
            };
        }),
        renderCaret,
    }), [renderCaret]);

    const refreshSurface = useCallback(() => {
        setSurfaceVersion((previous) => previous + 1);
    }, []);

    const emitEvent = useCallback((event: UserEvent) => {
        controller.handleEvent(event);
        refreshSurface();
    }, [controller, refreshSurface]);

    const switchMode = useCallback((nextMode: WorkspaceMode) => {
        emitEvent({ eventType: "switchMode", mode: nextMode });
        if (nextMode !== "label") {
            return;
        }
        const preferredEntry = entries.find((entry) => entry.visible) ?? entries[0];
        if (!preferredEntry) {
            return;
        }
        if (activeGroupId === preferredEntry.labelGroup.labelGroupId) {
            return;
        }
        setActiveGroupId(preferredEntry.labelGroup.labelGroupId);
        emitEvent({
            eventType: "switchLabelGroup",
            labelGroupId: preferredEntry.labelGroup.labelGroupId,
        });
    }, [activeGroupId, emitEvent, entries]);

    const activeEntryCanMutate = activeEntry
        ? (
            activeEntry.role === "editor"
            || activeEntry.role === "owner"
        )
        && activeEntry.visible
        && runtime.idRepo.getServerId("labelData", activeEntry.labelData.labelDataId) !== null
        : false;

    const canEditText = mode === "edit" && editChapterData.role !== "viewer";
    const canOperateOnSelection = activeEntryCanMutate && mode === "label" && selection.start < selection.end;

    const handleReloadFromError = useCallback(async () => {
        try {
            await onReloadChapterData();
            setErrors(null);
        } catch {
            return;
        }
    }, [onReloadChapterData]);

    const commitTextInsert = useCallback((insertedText: string) => {
        if (!canEditText || insertedText.length === 0) {
            return;
        }

        const { start, end } = normalizeSelection(caret);
        if (end > start) {
            emitEvent({
                eventType: "textOp",
                op: {
                    op: "delete",
                    start,
                    text: textSnapshot.slice(start, end),
                },
            });
        }

        emitEvent({
            eventType: "textOp",
            op: {
                op: "insert",
                start,
                text: insertedText,
            },
        });

        const nextPos = start + insertedText.length;
        setCaret({ anchor: nextPos, focus: nextPos, visible: true });
    }, [canEditText, caret, emitEvent, textSnapshot]);

    const commitTextDelete = useCallback((direction: "backward" | "forward") => {
        if (!canEditText) {
            return;
        }

        const { start, end } = normalizeSelection(caret);
        if (end > start) {
            emitEvent({
                eventType: "textOp",
                op: {
                    op: "delete",
                    start,
                    text: textSnapshot.slice(start, end),
                },
            });
            setCaret({ anchor: start, focus: start, visible: true });
            return;
        }

        if (direction === "backward" && start > 0) {
            const deleteStart = start - 1;
            emitEvent({
                eventType: "textOp",
                op: {
                    op: "delete",
                    start: deleteStart,
                    text: textSnapshot.slice(deleteStart, start),
                },
            });
            setCaret({ anchor: deleteStart, focus: deleteStart, visible: true });
            return;
        }

        if (direction === "forward" && start < textSnapshot.length) {
            emitEvent({
                eventType: "textOp",
                op: {
                    op: "delete",
                    start,
                    text: textSnapshot.slice(start, start + 1),
                },
            });
            setCaret({ anchor: start, focus: start, visible: true });
        }
    }, [canEditText, caret, emitEvent, textSnapshot]);

    const switchLabelGroup = useCallback((labelGroupId: ProvisionalId | null) => {
        setActiveGroupId(labelGroupId);
        setSelectedLabelId(null);
        emitEvent({
            eventType: "switchLabelGroup",
            labelGroupId,
        });
    }, [emitEvent]);

    const selectLabelAtPosition = useCallback((position: number) => {
        if (!activeEntry) {
            setSelectedLabelId(null);
            return;
        }
        const label = activeEntry.labels.find((candidate) => candidate.labelStart <= position && candidate.labelEnd > position) ?? null;
        setSelectedLabelId(label?.labelId ?? null);
    }, [activeEntry]);

    const addLabelFromSelection = useCallback(() => {
        if (!activeEntry || !canOperateOnSelection) {
            return;
        }
        const { start, end } = normalizeSelection(caret);
        emitEvent({
            eventType: "labelOp",
            labelGroupId: activeEntry.labelGroup.labelGroupId,
            op: {
                op: "add",
                startPos: start,
                endPos: end,
                word: textSnapshot.slice(start, end),
                dirty: true,
                entityGroup: null,
                score: 1,
            },
        });
    }, [activeEntry, canOperateOnSelection, caret, emitEvent, textSnapshot]);

    const deleteSelectedLabel = useCallback(() => {
        if (!activeEntry || !selectedLabel || !activeEntryCanMutate) {
            return;
        }
        emitEvent({
            eventType: "labelOp",
            labelGroupId: activeEntry.labelGroup.labelGroupId,
            op: {
                op: "delete",
                startPos: selectedLabel.labelStart,
                endPos: selectedLabel.labelEnd,
                word: selectedLabel.labelWord,
            },
        });
        setSelectedLabelId(null);
    }, [activeEntry, activeEntryCanMutate, emitEvent, selectedLabel]);

    const updateSelectedLabelFromSelection = useCallback(() => {
        if (!activeEntry || !selectedLabel || !canOperateOnSelection) {
            return;
        }
        const { start, end } = normalizeSelection(caret);
        emitEvent({
            eventType: "labelOp",
            labelGroupId: activeEntry.labelGroup.labelGroupId,
            op: {
                op: "update",
                startPos: selectedLabel.labelStart,
                endPos: selectedLabel.labelEnd,
                word: selectedLabel.labelWord,
                newStartPos: start,
                newEndPos: end,
                newWord: textSnapshot.slice(start, end),
                entityGroup: selectedLabel.labelEntityGroup,
                score: selectedLabel.labelScore,
                dirty: true,
            },
        });
    }, [activeEntry, canOperateOnSelection, caret, emitEvent, selectedLabel, textSnapshot]);

    const addLabelGroup = useCallback(() => {
        const trimmed = newGroupName.trim();
        if (!trimmed) {
            return;
        }
        emitEvent({
            eventType: "addLabelGroup",
            labelGroupName: trimmed,
        });
        setNewGroupName("");
    }, [emitEvent, newGroupName]);

    const errorMessages = extractErrorMessages(errors);
    const showOutdatedReload = errors?.some(isOutdatedError) ?? false;

    return (
        <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-6 text-slate-900 sm:px-6 lg:px-8">
            <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4">
                <Card className="overflow-visible border-0 bg-white/82 shadow-[0_20px_60px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader className="gap-4 border-b border-black/5 pb-5">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div className="space-y-3">
                                <div className="flex flex-wrap items-center gap-2">
                                    <StatusPill tone={isSyncing ? "warning" : "success"}>
                                        {isSyncing ? "Syncing" : "In Sync"}
                                    </StatusPill>
                                    <RoleTone role={editChapterData.role} />
                                    <StatusPill tone="default">
                                        {`Chapter ${editChapterData.chapter.chapterNum}`}
                                    </StatusPill>
                                </div>
                                <div className="space-y-1">
                                    <CardTitle className="text-2xl font-semibold tracking-tight text-slate-950">
                                        {novel.novelTitle}
                                    </CardTitle>
                                    <CardDescription className="text-base text-slate-600">
                                        {editChapterData.chapter.chapterTitle || `Chapter ${editChapterData.chapter.chapterNum}`}
                                    </CardDescription>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <Button
                                    type="button"
                                    variant={mode === "view" ? "default" : "secondary"}
                                    onClick={() => switchMode("view")}
                                >
                                    View
                                </Button>
                                <Button
                                    type="button"
                                    variant={mode === "edit" ? "default" : "secondary"}
                                    onClick={() => switchMode("edit")}
                                    disabled={editChapterData.role === "viewer"}
                                >
                                    Edit Text
                                </Button>
                                <Button
                                    type="button"
                                    variant={mode === "label" ? "default" : "secondary"}
                                    onClick={() => switchMode("label")}
                                >
                                    Label
                                </Button>
                                <Button type="button" variant="outline" onClick={() => void handleReloadFromError()}>
                                    Refresh Snapshot
                                </Button>
                            </div>
                        </div>
                        {errorMessages.length > 0 ? (
                            <div className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-left text-sm text-amber-950">
                                <div className="font-semibold">Editor needs attention</div>
                                <ul className="mt-2 space-y-1 text-amber-900">
                                    {errorMessages.map((message, index) => (
                                        <li key={`${message}-${index}`}>{message}</li>
                                    ))}
                                </ul>
                                {showOutdatedReload ? (
                                    <div className="mt-3">
                                        <Button type="button" size="sm" onClick={() => void handleReloadFromError()}>
                                            Reload Latest Chapter Content
                                        </Button>
                                    </div>
                                ) : null}
                            </div>
                        ) : null}
                    </CardHeader>
                </Card>

                <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)] 2xl:grid-cols-[280px_minmax(0,1.25fr)_minmax(320px,380px)]">
                    <Card className="border-0 bg-white/78 shadow-[0_12px_40px_rgba(38,29,18,0.08)] backdrop-blur xl:self-start">
                        <CardHeader className="border-b border-black/5 pb-4">
                            <CardTitle>Chapters</CardTitle>
                            <CardDescription>Switch chapters or add a new one without leaving the editor route.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="max-h-[26rem] space-y-2 overflow-auto pr-1">
                                {chapterList.map((chapter) => {
                                    const isCurrent = chapter.chapterId === editChapterData.chapter.chapterId;
                                    return (
                                        <button
                                            key={chapter.chapterId}
                                            type="button"
                                            onClick={() => onSelectChapter(chapter.chapterId)}
                                            className={`flex w-full flex-col rounded-2xl border px-4 py-3 text-left transition ${
                                                isCurrent
                                                    ? "border-amber-400 bg-amber-100/80 shadow-sm"
                                                    : "border-black/5 bg-white/70 hover:border-amber-300 hover:bg-amber-50/70"
                                            }`}
                                        >
                                            <span className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                                                Chapter {chapter.chapterNum}
                                            </span>
                                            <span className="mt-1 text-sm font-medium text-slate-900">
                                                {chapter.chapterTitle || `Chapter ${chapter.chapterNum}`}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                            <CreateChapterPanel
                                chapterDraftNum={chapterDraftNum}
                                chapterDraftTitle={chapterDraftTitle}
                                chapterDraftIsPublic={chapterDraftIsPublic}
                                createChapterError={createChapterError}
                                isCreatingChapter={isCreatingChapter}
                                disableCreation={editChapterData.role === "viewer"}
                                onChapterDraftNumChange={onChapterDraftNumChange}
                                onChapterDraftTitleChange={onChapterDraftTitleChange}
                                onChapterDraftVisibilityChange={onChapterDraftVisibilityChange}
                                onCreateChapter={onCreateChapter}
                            />
                        </CardContent>
                    </Card>

                    <Card className="min-w-0 border-0 bg-white/86 shadow-[0_16px_50px_rgba(38,29,18,0.1)] backdrop-blur">
                        <CardHeader className="border-b border-black/5 pb-4">
                            <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                                <div>
                                    <CardTitle>Chapter Surface</CardTitle>
                                    <CardDescription>
                                        {mode === "edit"
                                            ? "Type directly into the dynamic editor. Text edits flush through the controller/runtime."
                                            : mode === "label"
                                                ? "Select text, switch groups, and create or adjust labels."
                                                : "Review the chapter with label overlays active."}
                                    </CardDescription>
                                </div>
                                <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                                    <span>Selection [{selection.start}, {selection.end})</span>
                                    <span>{selectedText ? JSON.stringify(selectedText) : "No selection"}</span>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="rounded-[1.6rem] border border-black/8 bg-[linear-gradient(180deg,_rgba(255,255,255,0.95),_rgba(250,246,240,0.9))] p-4 shadow-inner sm:p-5">
                                <DynamicLabeledText
                                    caret={caret}
                                    manager={controller.uiManager}
                                    render={renderer}
                                    containerStyle={{
                                        minHeight: "32rem",
                                        padding: "1rem 1.1rem",
                                        borderRadius: "1.2rem",
                                        border: "1px solid rgba(15, 23, 42, 0.08)",
                                        background: "linear-gradient(180deg, rgba(255,255,255,0.94), rgba(248,244,236,0.94))",
                                        color: "#0f172a",
                                        fontFamily: "\"Iowan Old Style\", \"Palatino Linotype\", \"Book Antiqua\", serif",
                                        fontSize: "1.06rem",
                                        lineHeight: 1.9,
                                        whiteSpace: "pre-wrap",
                                        userSelect: "none",
                                        cursor: "text",
                                    }}
                                    onPointerDown={({ event }) => {
                                        event.preventDefault();
                                        setEditorActive(true);
                                        const position = resolvePointerPosition(
                                            event.target,
                                            event.clientX,
                                            event.clientY,
                                            controller.uiManager.getText().length,
                                        );
                                        dragAnchorRef.current = position;
                                        setCaret({ anchor: position, focus: position, visible: true });
                                        if (mode === "label") {
                                            emitEvent({ eventType: "hoverPos", pos: position });
                                        }
                                    }}
                                    onPointerMove={({ event }) => {
                                        const position = resolvePointerPosition(
                                            event.target,
                                            event.clientX,
                                            event.clientY,
                                            controller.uiManager.getText().length,
                                        );
                                        if (mode === "label") {
                                            emitEvent({ eventType: "hoverPos", pos: position });
                                        }
                                        if (dragAnchorRef.current === null || event.buttons === 0) {
                                            return;
                                        }
                                        setCaret({ anchor: dragAnchorRef.current, focus: position, visible: true });
                                    }}
                                    onPointerUp={({ event }) => {
                                        const position = resolvePointerPosition(
                                            event.target,
                                            event.clientX,
                                            event.clientY,
                                            controller.uiManager.getText().length,
                                        );
                                        if (dragAnchorRef.current !== null) {
                                            setCaret({ anchor: dragAnchorRef.current, focus: position, visible: true });
                                            dragAnchorRef.current = null;
                                        }
                                        if (mode === "label") {
                                            emitEvent({ eventType: "clickPos", pos: position });
                                            selectLabelAtPosition(position);
                                        }
                                    }}
                                    onDoubleClick={({ event }) => {
                                        const position = resolvePointerPosition(
                                            event.target,
                                            event.clientX,
                                            event.clientY,
                                            controller.uiManager.getText().length,
                                        );
                                        const bounds = findWordBounds(controller.uiManager.getText(), position);
                                        setCaret({ anchor: bounds.start, focus: bounds.end, visible: true });
                                        if (mode === "label") {
                                            emitEvent({ eventType: "clickPos", pos: position });
                                            selectLabelAtPosition(position);
                                        }
                                    }}
                                    onFocus={() => {
                                        setEditorActive(true);
                                        setCaret((previous) => ({ ...previous, visible: true }));
                                    }}
                                    onBlur={() => {
                                        dragAnchorRef.current = null;
                                        setEditorActive(false);
                                        setCaret((previous) => ({ ...previous, visible: false }));
                                        if (mode === "label") {
                                            emitEvent({ eventType: "hoverPos", pos: null });
                                        }
                                    }}
                                    onKeyDown={({ event }) => {
                                        const currentText = controller.uiManager.getText();
                                        const currentCaret = caret;
                                        const textLength = currentText.length;
                                        const extend = event.shiftKey;
                                        const baseStart = Math.min(currentCaret.anchor, currentCaret.focus);
                                        const baseEnd = Math.max(currentCaret.anchor, currentCaret.focus);

                                        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "a") {
                                            event.preventDefault();
                                            setCaret({ anchor: 0, focus: textLength, visible: true });
                                            return;
                                        }

                                        if ((event.metaKey || event.ctrlKey || event.altKey) && event.key.length === 1) {
                                            return;
                                        }

                                        if (event.key === "ArrowLeft") {
                                            event.preventDefault();
                                            const nextPos = clamp(extend ? currentCaret.focus - 1 : baseStart - 1, 0, textLength);
                                            setCaret(
                                                extend
                                                    ? { anchor: currentCaret.anchor, focus: nextPos, visible: true }
                                                    : { anchor: nextPos, focus: nextPos, visible: true },
                                            );
                                            return;
                                        }

                                        if (event.key === "ArrowRight") {
                                            event.preventDefault();
                                            const nextPos = clamp(extend ? currentCaret.focus + 1 : baseEnd + 1, 0, textLength);
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
                                            commitTextDelete("backward");
                                            return;
                                        }

                                        if (event.key === "Delete") {
                                            event.preventDefault();
                                            commitTextDelete("forward");
                                            return;
                                        }

                                        if (event.key === "Enter") {
                                            event.preventDefault();
                                            commitTextInsert("\n");
                                            return;
                                        }

                                        if (event.key === "Tab") {
                                            event.preventDefault();
                                            commitTextInsert("    ");
                                            return;
                                        }

                                        if (event.key.length === 1) {
                                            event.preventDefault();
                                            commitTextInsert(event.key);
                                        }
                                    }}
                                    onCopy={({ event }) => {
                                        const copiedText = selectionText(controller.uiManager.getText(), caret);
                                        if (!copiedText) {
                                            return;
                                        }
                                        event.preventDefault();
                                        event.clipboardData.setData("text/plain", copiedText);
                                    }}
                                    onCut={({ event }) => {
                                        const copiedText = selectionText(controller.uiManager.getText(), caret);
                                        if (!copiedText || !canEditText) {
                                            return;
                                        }
                                        event.preventDefault();
                                        event.clipboardData.setData("text/plain", copiedText);
                                        commitTextDelete("backward");
                                    }}
                                    onPaste={({ event }) => {
                                        if (!canEditText) {
                                            return;
                                        }
                                        const pastedText = event.clipboardData.getData("text/plain");
                                        if (!pastedText) {
                                            return;
                                        }
                                        event.preventDefault();
                                        commitTextInsert(pastedText);
                                    }}
                                    onInput={({ event }) => {
                                        event.currentTarget.textContent = "";
                                    }}
                                />
                            </div>
                            <div className="grid gap-3 lg:grid-cols-3">
                                <div className="rounded-2xl border border-black/5 bg-slate-950/[0.03] px-4 py-3">
                                    <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Editor state</div>
                                    <div className="mt-2 space-y-1 text-sm text-slate-700">
                                        <div>{editorActive ? "Focused" : "Blurred"}</div>
                                        <div>{textSnapshot.length} characters</div>
                                    </div>
                                </div>
                                <div className="rounded-2xl border border-black/5 bg-slate-950/[0.03] px-4 py-3">
                                    <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Selection</div>
                                    <div className="mt-2 space-y-1 text-sm text-slate-700">
                                        <div>[{selection.start}, {selection.end})</div>
                                        <div>{selectedText ? selectedText : "No text selected"}</div>
                                    </div>
                                </div>
                                <div className="rounded-2xl border border-black/5 bg-slate-950/[0.03] px-4 py-3">
                                    <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Sync</div>
                                    <div className="mt-2 space-y-1 text-sm text-slate-700">
                                        <div>{isSyncing ? "Pending requests are being flushed" : "No queued requests"}</div>
                                        <div>{mode === "edit" ? "Text mode" : mode === "label" ? "Label mode" : "Read-only mode"}</div>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="border-0 bg-white/80 shadow-[0_14px_44px_rgba(38,29,18,0.09)] backdrop-blur xl:col-span-2 2xl:col-span-1 2xl:self-start">
                        <CardHeader className="border-b border-black/5 pb-4">
                            <CardTitle>Labels</CardTitle>
                            <CardDescription>Switch groups, stage new label groups, and adjust labels from the active selection.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-5">
                            <div className="space-y-2">
                                <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Label groups</div>
                                <div className="space-y-2">
                                    {entries.map((entry) => {
                                        const currentServerId = runtime.idRepo.getServerId("labelData", entry.labelData.labelDataId);
                                        const isActive = entry.labelGroup.labelGroupId === activeGroupId;
                                        const isReady = currentServerId !== null;
                                        const canMutate = entry.visible && isReady && (entry.role === "editor" || entry.role === "owner");
                                        const statusLabel = !entry.visible
                                            ? "not loaded"
                                            : !isReady
                                                ? "preparing"
                                                : canMutate
                                                    ? "editable"
                                                    : "view only";

                                        return (
                                            <button
                                                key={entry.labelGroup.labelGroupId}
                                                type="button"
                                                onClick={() => switchLabelGroup(entry.labelGroup.labelGroupId)}
                                                className={`flex w-full items-start justify-between rounded-2xl border px-4 py-3 text-left transition ${
                                                    isActive
                                                        ? "border-amber-400 bg-amber-100/80"
                                                        : "border-black/5 bg-white/70 hover:border-amber-300 hover:bg-amber-50/70"
                                                }`}
                                            >
                                                <div className="space-y-1">
                                                    <div className="flex items-center gap-2">
                                                        <span
                                                            className="h-3 w-3 rounded-full border border-black/10"
                                                            style={{ backgroundColor: toHex(runtime.colourMapping.get(entry.labelGroup.labelGroupId) ?? 0) }}
                                                        />
                                                        <span className="text-sm font-medium text-slate-900">
                                                            {entry.labelGroup.labelGroupName}
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-slate-500">
                                                        {entry.labels.length} labels
                                                    </div>
                                                </div>
                                                <div className="flex flex-col items-end gap-2">
                                                    <RoleTone role={entry.role} />
                                                    <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                                                        {statusLabel}
                                                    </span>
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="space-y-3 rounded-2xl border border-black/5 bg-slate-950/[0.03] p-4">
                                <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">New label group</div>
                                <input
                                    value={newGroupName}
                                    onChange={(event) => setNewGroupName(event.target.value)}
                                    placeholder="Character glossary"
                                    className="w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-amber-400"
                                />
                                <Button type="button" className="w-full" onClick={addLabelGroup} disabled={newGroupName.trim().length === 0}>
                                    Add Label Group
                                </Button>
                            </div>

                            <div className="space-y-3 rounded-2xl border border-black/5 bg-slate-950/[0.03] p-4">
                                <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Active group controls</div>
                                {activeEntry ? (
                                    <div className="space-y-3">
                                        <div className="rounded-xl border border-black/5 bg-white/80 px-3 py-2 text-sm text-slate-700">
                                            {activeEntry.labelGroup.labelGroupName}
                                        </div>
                                        <div className="grid gap-2 sm:grid-cols-2">
                                            <Button type="button" variant="secondary" onClick={addLabelFromSelection} disabled={!canOperateOnSelection}>
                                                Add From Selection
                                            </Button>
                                            <Button type="button" variant="secondary" onClick={updateSelectedLabelFromSelection} disabled={!selectedLabel || !canOperateOnSelection}>
                                                Use Selection For Label
                                            </Button>
                                            <Button type="button" variant="outline" onClick={deleteSelectedLabel} disabled={!selectedLabel || !activeEntryCanMutate}>
                                                Remove Selected Label
                                            </Button>
                                            <Button type="button" variant="outline" onClick={() => setSelectedLabelId(null)} disabled={!selectedLabel}>
                                                Clear Label Selection
                                            </Button>
                                        </div>
                                        {!activeEntry.visible ? (
                                            <p className="text-xs text-slate-500">
                                                This group exists, but its labels were not included in the current editor snapshot.
                                            </p>
                                        ) : null}
                                        {activeEntry.visible && !activeEntryCanMutate ? (
                                            <p className="text-xs text-slate-500">
                                                This group is visible, but it is not ready for writes yet or your role is read-only.
                                            </p>
                                        ) : null}
                                    </div>
                                ) : (
                                    <p className="text-sm text-slate-500">Choose a label group to start labeling.</p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Labels in active group</div>
                                <div className="max-h-[28rem] space-y-2 overflow-auto pr-1">
                                    {activeEntry?.labels.length ? activeEntry.labels.map((label) => {
                                        const isSelected = label.labelId === selectedLabelId;
                                        return (
                                            <button
                                                key={label.labelId}
                                                type="button"
                                                onClick={() => setSelectedLabelId(label.labelId)}
                                                className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                                                    isSelected
                                                        ? "border-amber-400 bg-amber-100/80"
                                                        : "border-black/5 bg-white/75 hover:border-amber-300 hover:bg-amber-50/70"
                                                }`}
                                            >
                                                <div className="flex items-start justify-between gap-3">
                                                    <div>
                                                        <div className="text-sm font-medium text-slate-900">{label.labelWord}</div>
                                                        <div className="mt-1 text-xs text-slate-500">
                                                            [{label.labelStart}, {label.labelEnd}) {label.labelEntityGroup ? `• ${label.labelEntityGroup}` : ""}
                                                        </div>
                                                    </div>
                                                    <LabelStateBadge label={label} />
                                                </div>
                                                <div className="mt-2 text-xs text-slate-500">
                                                    Score {label.labelScore.toFixed(2)}
                                                </div>
                                            </button>
                                        );
                                    }) : (
                                        <div className="rounded-2xl border border-dashed border-black/10 bg-white/60 px-4 py-4 text-sm text-slate-500">
                                            {activeEntry
                                                ? "No labels in this group yet."
                                                : "No active label group selected."}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </main>
    );
}

export function EditNovelPage({ loadLabelsNum = 3 }: { loadLabelsNum: number }) {
    const params = useParams<"novelId">();
    const [searchParams, setSearchParams] = useSearchParams();
    const chapterId = useMemo(
        () => extractParams.edit.novel(searchParams).chapterId,
        [searchParams],
    );

    const novelId = params.novelId ?? null;
    const [chapterDraftNum, setChapterDraftNum] = useState("1");
    const [chapterDraftTitle, setChapterDraftTitle] = useState("");
    const [chapterDraftIsPublic, setChapterDraftIsPublic] = useState(false);
    const [createChapterError, setCreateChapterError] = useState<string | null>(null);
    const [isCreatingChapter, setIsCreatingChapter] = useState(false);

    const [novel, novelLoading, novelError, reloadNovel] = useLoader<Novel | null>(
        null,
        () => {
            if (!novelId) {
                return Promise.reject(new Error("No novel ID provided in the URL."));
            }
            return loadNovel(novelId);
        },
        [novelId],
    );

    const [chapterList, chapterListLoading, chapterListError, reloadChapterList] = useLoader<Chapter[]>(
        [],
        () => {
            if (!novelId) {
                return Promise.reject(new Error("No novel ID provided in the URL."));
            }
            return loadChapters(novelId);
        },
        [novelId],
    );

    const [editChapterData, editChapterDataLoading, editChapterDataError, reloadEditChapterData] = useLoader<EditChapterData | null>(
        null,
        () => {
            if (!novelId || !chapterId) {
                return Promise.resolve(null);
            }
            return loadEditChapterData(chapterId, novelId, loadLabelsNum);
        },
        [chapterId, loadLabelsNum, novelId],
    );

    const setChapterSearchParam = useCallback((nextChapterId: string) => {
        const nextParams = new URLSearchParams(searchParams);
        nextParams.set("chapter-id", nextChapterId);
        setSearchParams(nextParams, { replace: true });
    }, [searchParams, setSearchParams]);

    useEffect(() => {
        setChapterDraftNum(String(getSuggestedChapterNumber(chapterList)));
    }, [chapterList]);

    useEffect(() => {
        if (chapterListLoading || chapterList.length === 0 || chapterId) {
            return;
        }
        setChapterSearchParam(chapterList[0].chapterId);
    }, [chapterId, chapterList, chapterListLoading, setChapterSearchParam]);

    const invalidSelectedChapter = Boolean(
        chapterId
        && chapterList.length > 0
        && !chapterList.some((chapter) => chapter.chapterId === chapterId),
    );

    const refreshAll = useCallback(async () => {
        await Promise.allSettled([
            reloadNovel(),
            reloadChapterList(),
            reloadEditChapterData(),
        ]);
    }, [reloadChapterList, reloadEditChapterData, reloadNovel]);

    const createChapter = useCallback(async () => {
        if (!novelId) {
            setCreateChapterError("Missing novel ID.");
            return;
        }

        const chapterNum = Number(chapterDraftNum);
        if (!Number.isInteger(chapterNum) || chapterNum <= 0) {
            setCreateChapterError("Chapter number must be a positive integer.");
            return;
        }

        setCreateChapterError(null);
        setIsCreatingChapter(true);
        try {
            const response = await createChapterNovelsNovelIdChaptersPost({
                path: { novelId },
                body: {
                    chapterNum,
                    chapterTitle: chapterDraftTitle.trim(),
                    chapterIsPublic: chapterDraftIsPublic,
                },
            });

            if (!response.data) {
                setCreateChapterError(formatUnknownError(response.error ?? new Error("Failed to create chapter.")));
                return;
            }

            setChapterDraftTitle("");
            setChapterDraftIsPublic(false);
            await reloadChapterList();
            setChapterSearchParam(response.data.metadata.chapterId);
        } catch (error) {
            setCreateChapterError(formatUnknownError(error));
        } finally {
            setIsCreatingChapter(false);
        }
    }, [
        chapterDraftIsPublic,
        chapterDraftNum,
        chapterDraftTitle,
        novelId,
        reloadChapterList,
        setChapterSearchParam,
    ]);

    if (!novelId) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-stone-100 px-4 py-10">
                <Card className="max-w-lg border-0 bg-white/85 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>Missing novel ID</CardTitle>
                        <CardDescription>The edit route requires a `novelId` path parameter.</CardDescription>
                    </CardHeader>
                </Card>
            </main>
        );
    }

    const loadingBaseState = novelLoading || chapterListLoading || (Boolean(chapterId) && !editChapterData && editChapterDataLoading);
    const topLevelError = novelError ?? chapterListError;

    if (loadingBaseState && !novel && chapterList.length === 0) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-10">
                <Card className="max-w-xl border-0 bg-white/80 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>Preparing the editor</CardTitle>
                        <CardDescription>Loading the novel, chapters, and the current chapter snapshot.</CardDescription>
                    </CardHeader>
                </Card>
            </main>
        );
    }

    if (topLevelError) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-10">
                <Card className="max-w-xl border-0 bg-white/85 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>Couldn’t load the editor shell</CardTitle>
                        <CardDescription>{formatUnknownError(topLevelError)}</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button type="button" onClick={() => void refreshAll()}>
                            Retry
                        </Button>
                    </CardContent>
                </Card>
            </main>
        );
    }

    if (chapterList.length === 0) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-10">
                <Card className="max-w-xl border-0 bg-white/85 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>No chapters yet</CardTitle>
                        <CardDescription>Create the first chapter here, then the editor will open automatically.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <CreateChapterPanel
                            chapterDraftNum={chapterDraftNum}
                            chapterDraftTitle={chapterDraftTitle}
                            chapterDraftIsPublic={chapterDraftIsPublic}
                            createChapterError={createChapterError}
                            isCreatingChapter={isCreatingChapter}
                            onChapterDraftNumChange={setChapterDraftNum}
                            onChapterDraftTitleChange={setChapterDraftTitle}
                            onChapterDraftVisibilityChange={setChapterDraftIsPublic}
                            onCreateChapter={createChapter}
                        />
                    </CardContent>
                </Card>
            </main>
        );
    }

    if (invalidSelectedChapter) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-10">
                <Card className="max-w-xl border-0 bg-white/85 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>Selected chapter not found</CardTitle>
                        <CardDescription>The current `chapter-id` query parameter does not match any chapter in this novel.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button type="button" onClick={() => setChapterSearchParam(chapterList[0].chapterId)}>
                            Jump To First Chapter
                        </Button>
                    </CardContent>
                </Card>
            </main>
        );
    }

    if (!chapterId) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-10">
                <Card className="max-w-xl border-0 bg-white/85 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>Selecting the first chapter</CardTitle>
                        <CardDescription>The editor is waiting for the route state to settle.</CardDescription>
                    </CardHeader>
                </Card>
            </main>
        );
    }

    if (editChapterDataError) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-10">
                <Card className="max-w-xl border-0 bg-white/85 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>Couldn’t load this chapter snapshot</CardTitle>
                        <CardDescription>{formatUnknownError(editChapterDataError)}</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button type="button" onClick={() => void reloadEditChapterData()}>
                            Retry Chapter Load
                        </Button>
                    </CardContent>
                </Card>
            </main>
        );
    }

    if (!novel || !editChapterData) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(245,187,110,0.24),_transparent_34%),linear-gradient(180deg,_#f8f3ea_0%,_#f4efe5_32%,_#efe8dc_100%)] px-4 py-10">
                <Card className="max-w-xl border-0 bg-white/85 text-left shadow-[0_18px_50px_rgba(38,29,18,0.12)] backdrop-blur">
                    <CardHeader>
                        <CardTitle>Editor data unavailable</CardTitle>
                        <CardDescription>The editor prototype needs the chapter snapshot before it can mount.</CardDescription>
                    </CardHeader>
                </Card>
            </main>
        );
    }

    return (
        <EditNovelWorkspace
            key={`${editChapterData.chapter.chapterId}:${editChapterData.chapterContent.chapterContentId}`}
            editChapterData={editChapterData}
            novel={novel}
            chapterList={chapterList}
            chapterDraftNum={chapterDraftNum}
            chapterDraftTitle={chapterDraftTitle}
            chapterDraftIsPublic={chapterDraftIsPublic}
            createChapterError={createChapterError}
            isCreatingChapter={isCreatingChapter}
            onChapterDraftNumChange={setChapterDraftNum}
            onChapterDraftTitleChange={setChapterDraftTitle}
            onChapterDraftVisibilityChange={setChapterDraftIsPublic}
            onCreateChapter={createChapter}
            onReloadChapterData={reloadEditChapterData}
            onSelectChapter={setChapterSearchParam}
        />
    );
}
