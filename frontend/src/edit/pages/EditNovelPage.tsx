import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
    useSyncExternalStore,
    type JSX,
    type RefObject,
} from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import {
    createChapterNovelsNovelIdChaptersPost,
    readChaptersByNovelChaptersGet,
    readEditChapterDataEditChapterDataChapterIdGet,
    readNovelNovelsNovelIdGet,
    readUserMeUsersMeGet,
    type Chapter,
    type DetailHttpErrorResponse,
    type EditChapterData,
    type Label,
    type Novel,
    type RequestConflictErrorResponse,
    type Role,
    type User,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLoader } from "@/lib/utils";
import { AppRoutes, extractParams } from "@/routes";

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
    currentUser: User;
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

type LabelPopupRef = {
    labelGroupId: ProvisionalId;
    labelId: ProvisionalId;
};

type LabelPopupState =
    | { type: "selection"; x: number; y: number }
    | { type: "labels"; x: number; y: number; candidates: LabelPopupRef[]; selectedIndex: number }
    | null;

type ResolvedLabelRef = {
    labelGroupId: ProvisionalId;
    labelGroupName: string;
    color: number;
    role: Role;
    label: Label;
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

async function loadCurrentUser(): Promise<User> {
    const response = await readUserMeUsersMeGet();
    if (!response.data) {
        throw new Error("Failed to load current user.");
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
    currentUser,
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
    const [selectedLabelRef, setSelectedLabelRef] = useState<LabelPopupRef | null>(null);
    const [newGroupName, setNewGroupName] = useState("");
    const [, setSurfaceVersion] = useState(0);
    const [isSyncing, setIsSyncing] = useState(false);
    const [toolPanel, setToolPanel] = useState("mode");
    const [labelPopup, setLabelPopup] = useState<LabelPopupState>(null);
    const [labelEntityGroup, setLabelEntityGroup] = useState("");
    const [labelScore, setLabelScore] = useState("1");
    const [labelDirty, setLabelDirty] = useState(true);
    const dragAnchorRef = useRef<number | null>(null);
    const modeRef = useRef<WorkspaceMode>(mode);

    useEffect(() => {
        modeRef.current = mode;
    }, [mode]);

    const getMode = useCallback(() => modeRef.current, []);

    const runtime = useMemo(
        () => buildRuntime(
            setErrors,
            novel,
            editChapterData.chapter,
            editChapterData,
            currentUser.userId,
        ),
        [currentUser.userId, editChapterData, novel],
    );

    const controller = useController(
        editChapterData,
        getMode,
        setMode,
        runtime,
        setErrors,
    );

    const segmentManager = controller.uiManager.segmentManager;
    const subscribeToSegmentManager = useCallback(
        (onStoreChange: () => void) => segmentManager.subscribe(onStoreChange),
        [segmentManager],
    );
    const getSegmentTextSnapshot = useCallback(
        () => segmentManager.getText(),
        [segmentManager],
    );
    const textSnapshot = useSyncExternalStore(
        subscribeToSegmentManager,
        getSegmentTextSnapshot,
        getSegmentTextSnapshot,
    );

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

    useEffect(() => {
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setLabelPopup(null);
            }
        };
        const closeOnOutsidePointer = (event: PointerEvent) => {
            const target = event.target;
            if (target instanceof Element && target.closest("[data-label-popup]")) {
                return;
            }
            setLabelPopup(null);
        };
        window.addEventListener("keydown", closeOnEscape);
        window.addEventListener("pointerdown", closeOnOutsidePointer);
        return () => {
            window.removeEventListener("keydown", closeOnEscape);
            window.removeEventListener("pointerdown", closeOnOutsidePointer);
        };
    }, []);

    const labelGroupViews = controller.labelGroupViews;
    const activeGroupId = controller.activeLabelGroupId;
    const activeGroupView = labelGroupViews.find((group) => group.labelGroupId === activeGroupId) ?? null;
    const activeLabels = activeGroupId ? runtime.dataManager.getForGroup.labels(activeGroupId) : [];
    const selection = normalizeSelection(caret);
    const selectedText = selectionText(textSnapshot, caret);

    const resolveLabelRef = useCallback((ref: LabelPopupRef | null): ResolvedLabelRef | null => {
        if (!ref) {
            return null;
        }
        const group = labelGroupViews.find((candidate) => candidate.labelGroupId === ref.labelGroupId);
        if (!group) {
            return null;
        }
        const label = runtime.dataManager.getForGroup.labels(ref.labelGroupId).find((candidate) => candidate.labelId === ref.labelId);
        if (!label) {
            return null;
        }
        return {
            labelGroupId: ref.labelGroupId,
            labelGroupName: group.labelGroupName,
            color: group.color,
            role: group.role,
            label,
        };
    }, [labelGroupViews, runtime]);

    const selectedLabel = resolveLabelRef(selectedLabelRef);

    const clickedPopupLabels = useMemo(() => {
        if (labelPopup?.type !== "labels") {
            return [];
        }
        return labelPopup.candidates
            .map((candidate) => resolveLabelRef(candidate))
            .filter((candidate): candidate is ResolvedLabelRef => candidate !== null);
    }, [labelPopup, resolveLabelRef]);

    const clickedPopupLabel = labelPopup?.type === "labels"
        ? clickedPopupLabels[labelPopup.selectedIndex] ?? clickedPopupLabels[0] ?? null
        : null;

    const findLabelsAtPosition = useCallback((position: number): LabelPopupRef[] => (
        labelGroupViews
            .filter((group) => group.visible)
            .flatMap((group) => runtime.dataManager.getForGroup.labels(group.labelGroupId)
                .filter((label) => label.labelStart <= position && label.labelEnd > position)
                .map((label) => ({
                    labelGroupId: group.labelGroupId,
                    labelId: label.labelId,
                })))
    ), [labelGroupViews, runtime]);

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

    const switchLabelGroup = useCallback((labelGroupId: ProvisionalId | null) => {
        setSelectedLabelRef(null);
        emitEvent({
            eventType: "switchLabelGroup",
            labelGroupId,
        });
    }, [emitEvent]);

    const switchMode = useCallback((nextMode: WorkspaceMode) => {
        setLabelPopup(null);
        emitEvent({ eventType: "switchMode", mode: nextMode });
        if (nextMode !== "label") {
            return;
        }
        const preferredGroup = labelGroupViews.find((group) => group.visible) ?? labelGroupViews[0];
        if (!preferredGroup) {
            return;
        }
        if (activeGroupId === preferredGroup.labelGroupId) {
            return;
        }
        switchLabelGroup(preferredGroup.labelGroupId);
    }, [activeGroupId, emitEvent, labelGroupViews, switchLabelGroup]);

    const activeGroupCanMutate = activeGroupView
        ? (
            activeGroupView.role === "editor"
            || activeGroupView.role === "owner"
        )
        : false;

    const canEditText = mode === "edit" && editChapterData.role !== "viewer";
    const canOperateOnSelection = activeGroupCanMutate && mode === "label" && selection.start < selection.end;

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

    const selectLabelAtPosition = useCallback((position: number) => {
        const clicked = findLabelsAtPosition(position);
        if (clicked.length === 0) {
            setSelectedLabelRef(null);
            return;
        }
        setSelectedLabelRef(clicked[0]);
    }, [findLabelsAtPosition]);

    const addLabelFromSelection = useCallback((groupId = activeGroupId) => {
        const group = groupId ? labelGroupViews.find((candidate) => candidate.labelGroupId === groupId) : null;
        const canMutateGroup = group?.role === "editor" || group?.role === "owner";
        if (!groupId || !canMutateGroup || mode !== "label" || selection.start >= selection.end) {
            return;
        }
        const { start, end } = normalizeSelection(caret);
        const parsedScore = Number(labelScore);
        emitEvent({
            eventType: "labelOp",
            labelGroupId: groupId,
            op: {
                op: "add",
                startPos: start,
                endPos: end,
                word: textSnapshot.slice(start, end),
                dirty: labelDirty,
                entityGroup: labelEntityGroup.trim() || null,
                score: Number.isFinite(parsedScore) ? parsedScore : 1,
            },
        });
        setLabelPopup(null);
    }, [activeGroupId, caret, emitEvent, labelDirty, labelEntityGroup, labelGroupViews, labelScore, mode, selection.end, selection.start, textSnapshot]);

    const deleteLabelRef = useCallback((target: ResolvedLabelRef | null) => {
        if (!target || !(target.role === "editor" || target.role === "owner")) {
            return;
        }
        emitEvent({
            eventType: "labelOp",
            labelGroupId: target.labelGroupId,
            op: {
                op: "delete",
                startPos: target.label.labelStart,
                endPos: target.label.labelEnd,
                word: target.label.labelWord,
            },
        });
        setSelectedLabelRef(null);
        setLabelPopup(null);
    }, [emitEvent]);

    const updateLabelFromSelection = useCallback((target: ResolvedLabelRef | null) => {
        if (!target || !(target.role === "editor" || target.role === "owner") || mode !== "label" || selection.start >= selection.end) {
            return;
        }
        const { start, end } = normalizeSelection(caret);
        const parsedScore = Number(labelScore);
        emitEvent({
            eventType: "labelOp",
            labelGroupId: target.labelGroupId,
            op: {
                op: "update",
                startPos: target.label.labelStart,
                endPos: target.label.labelEnd,
                word: target.label.labelWord,
                newStartPos: start,
                newEndPos: end,
                newWord: textSnapshot.slice(start, end),
                entityGroup: labelEntityGroup.trim() || null,
                score: Number.isFinite(parsedScore) ? parsedScore : target.label.labelScore,
                dirty: labelDirty,
            },
        });
        setLabelPopup(null);
    }, [caret, emitEvent, labelDirty, labelEntityGroup, labelScore, mode, selection.end, selection.start, textSnapshot]);

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

    const toggleLabelGroupVisibility = useCallback((labelGroupId: ProvisionalId, visible: boolean) => {
        emitEvent({ eventType: "toggleVisibility", labelGroupId, visible });
    }, [emitEvent]);

    const reloadLabelGroup = useCallback((labelGroupId: ProvisionalId) => {
        emitEvent({ eventType: "loadGroup", labelGroupId });
    }, [emitEvent]);

    const errorMessages = extractErrorMessages(errors);
    const showOutdatedReload = errors?.some(isOutdatedError) ?? false;

    const popupGroupId = activeGroupId ?? labelGroupViews[0]?.labelGroupId ?? null;

    return (
        <main className="min-h-screen bg-[#f6f2ea] text-slate-900">
            <header className="sticky top-0 z-30 border-b border-black/10 bg-white/90 px-4 py-3 backdrop-blur sm:px-6">
                <div className="mx-auto flex w-full max-w-[1680px] flex-wrap items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                        <Button type="button" variant="outline" asChild>
                            <Link to={AppRoutes.DASHBOARD}>Home</Link>
                        </Button>
                        <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-slate-950">{novel.novelTitle}</div>
                            <div className="truncate text-xs text-slate-500">
                                Chapter {editChapterData.chapter.chapterNum}
                                {editChapterData.chapter.chapterTitle ? `: ${editChapterData.chapter.chapterTitle}` : ""}
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <select
                            value={editChapterData.chapter.chapterId}
                            onChange={(event) => onSelectChapter(event.target.value)}
                            className="h-9 rounded-md border border-black/10 bg-white px-3 text-sm outline-none"
                        >
                            {chapterList.map((chapter) => (
                                <option key={chapter.chapterId} value={chapter.chapterId}>
                                    Chapter {chapter.chapterNum}: {chapter.chapterTitle || `Chapter ${chapter.chapterNum}`}
                                </option>
                            ))}
                        </select>
                        <StatusPill tone={isSyncing ? "warning" : "success"}>{isSyncing ? "Syncing" : "In Sync"}</StatusPill>
                        <RoleTone role={editChapterData.role} />
                        <Button type="button" variant="outline" onClick={() => void handleReloadFromError()}>
                            Refresh
                        </Button>
                    </div>
                </div>
                {errorMessages.length > 0 ? (
                    <div className="mx-auto mt-3 w-full max-w-[1680px] rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
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
            </header>

            <div className="mx-auto grid w-full max-w-[1680px] gap-5 px-4 py-5 lg:grid-cols-[minmax(0,1fr)_380px] sm:px-6">
                <section className="min-w-0">
                    <div className="mx-auto min-h-[calc(100vh-7rem)] max-w-[920px] bg-white px-6 py-8 shadow-[0_18px_60px_rgba(30,24,16,0.14)] sm:px-10 lg:px-14">
                        <div className="mb-6 flex flex-wrap items-start justify-between gap-3 border-b border-black/10 pb-4">
                            <div>
                                <h1 className="text-xl font-semibold text-slate-950">
                                    {editChapterData.chapter.chapterTitle || `Chapter ${editChapterData.chapter.chapterNum}`}
                                </h1>
                                <p className="mt-1 text-sm text-slate-500">
                                    {mode === "edit" ? "Text editing" : mode === "label" ? "Labeling" : "Reading"} mode
                                </p>
                            </div>
                            <div className="text-right text-xs text-slate-500">
                                <div>{textSnapshot.length} characters</div>
                                <div>Selection [{selection.start}, {selection.end})</div>
                            </div>
                        </div>

                        <DynamicLabeledText
                                    caret={caret}
                                    manager={segmentManager}
                                    render={renderer}
                                    containerStyle={{
                                        minHeight: "calc(100vh - 16rem)",
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
                                        setLabelPopup(null);
                                        const position = resolvePointerPosition(
                                            event.target,
                                            event.clientX,
                                            event.clientY,
                                            segmentManager.getText().length,
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
                                            segmentManager.getText().length,
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
                                            segmentManager.getText().length,
                                        );
                                        const anchor = dragAnchorRef.current;
                                        const nextCaret = anchor !== null
                                            ? { anchor, focus: position, visible: true }
                                            : { anchor: position, focus: position, visible: true };
                                        setCaret(nextCaret);
                                        dragAnchorRef.current = null;
                                        if (mode === "label") {
                                            emitEvent({ eventType: "clickPos", pos: position });
                                            const start = Math.min(nextCaret.anchor, nextCaret.focus);
                                            const end = Math.max(nextCaret.anchor, nextCaret.focus);
                                            if (start < end) {
                                                setLabelPopup({ type: "selection", x: event.clientX, y: event.clientY });
                                            } else {
                                                const candidates = findLabelsAtPosition(position);
                                                selectLabelAtPosition(position);
                                                setLabelPopup(candidates.length > 0
                                                    ? { type: "labels", x: event.clientX, y: event.clientY, candidates, selectedIndex: 0 }
                                                    : null);
                                            }
                                        }
                                    }}
                                    onDoubleClick={({ event }) => {
                                        const position = resolvePointerPosition(
                                            event.target,
                                            event.clientX,
                                            event.clientY,
                                            segmentManager.getText().length,
                                        );
                                        const bounds = findWordBounds(segmentManager.getText(), position);
                                        setCaret({ anchor: bounds.start, focus: bounds.end, visible: true });
                                        if (mode === "label") {
                                            emitEvent({ eventType: "clickPos", pos: position });
                                            setLabelPopup({ type: "selection", x: event.clientX, y: event.clientY });
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
                                        const currentText = segmentManager.getText();
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
                                        const copiedText = selectionText(segmentManager.getText(), caret);
                                        if (!copiedText) {
                                            return;
                                        }
                                        event.preventDefault();
                                        event.clipboardData.setData("text/plain", copiedText);
                                    }}
                                    onCut={({ event }) => {
                                        const copiedText = selectionText(segmentManager.getText(), caret);
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
                </section>

                <aside className="lg:sticky lg:top-[5.25rem] lg:h-[calc(100vh-6.5rem)]">
                    <Card className="h-full overflow-hidden border-0 bg-white shadow-[0_14px_44px_rgba(38,29,18,0.1)]">
                        <CardHeader className="border-b border-black/5 pb-4">
                            <CardTitle>Tools</CardTitle>
                            <CardDescription>Mode controls, labels, chapters, and future automation panels.</CardDescription>
                        </CardHeader>
                        <CardContent className="h-[calc(100%-5.5rem)] overflow-auto px-4 py-4">
                            <Tabs value={toolPanel} onValueChange={setToolPanel} className="h-full">
                                <TabsList className="grid grid-cols-4">
                                    <TabsTrigger value="mode">Mode</TabsTrigger>
                                    <TabsTrigger value="labels">Labels</TabsTrigger>
                                    <TabsTrigger value="chapters">Chapters</TabsTrigger>
                                    <TabsTrigger value="future">More</TabsTrigger>
                                </TabsList>

                                <TabsContent value="mode" className="space-y-4 pt-3">
                                    <div className="grid grid-cols-3 gap-2">
                                        <Button type="button" variant={mode === "view" ? "default" : "secondary"} onClick={() => switchMode("view")}>View</Button>
                                        <Button type="button" variant={mode === "edit" ? "default" : "secondary"} onClick={() => switchMode("edit")} disabled={editChapterData.role === "viewer"}>Edit</Button>
                                        <Button type="button" variant={mode === "label" ? "default" : "secondary"} onClick={() => switchMode("label")}>Label</Button>
                                    </div>
                                    <div className="rounded-lg border border-black/10 bg-slate-50 p-3 text-sm text-slate-700">
                                        <div>{editorActive ? "Editor focused" : "Editor blurred"}</div>
                                        <div>{textSnapshot.length} characters</div>
                                        <div>Selection [{selection.start}, {selection.end})</div>
                                        <div className="truncate">{selectedText || "No selected text"}</div>
                                    </div>
                                </TabsContent>

                                <TabsContent value="labels" className="space-y-4 pt-3">
                                    <div className="space-y-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Label groups</div>
                                        {labelGroupViews.map((group) => {
                                            const labels = runtime.dataManager.getForGroup.labels(group.labelGroupId);
                                            const isActive = group.labelGroupId === activeGroupId;
                                            return (
                                                <div key={group.labelGroupId} className={`rounded-lg border p-3 ${isActive ? "border-amber-400 bg-amber-50" : "border-black/10 bg-white"}`}>
                                                    <button type="button" className="flex w-full items-start justify-between gap-3 text-left" onClick={() => switchLabelGroup(group.labelGroupId)}>
                                                        <span className="min-w-0">
                                                            <span className="flex items-center gap-2">
                                                                <span className="h-3 w-3 rounded-full border border-black/10" style={{ backgroundColor: toHex(group.color) }} />
                                                                <span className="truncate text-sm font-medium text-slate-900">{group.labelGroupName}</span>
                                                            </span>
                                                            <span className="mt-1 block text-xs text-slate-500">{labels.length} labels, {group.loadingStatus}</span>
                                                        </span>
                                                        <RoleTone role={group.role} />
                                                    </button>
                                                    <div className="mt-3 grid grid-cols-2 gap-2">
                                                        <Button type="button" size="sm" variant="outline" onClick={() => toggleLabelGroupVisibility(group.labelGroupId, !group.visible)}>
                                                            {group.visible ? "Hide" : "Show"}
                                                        </Button>
                                                        <Button type="button" size="sm" variant="outline" onClick={() => reloadLabelGroup(group.labelGroupId)}>
                                                            Refresh
                                                        </Button>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>

                                    <div className="space-y-3 rounded-lg border border-black/10 bg-slate-50 p-3">
                                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">New label group</div>
                                        <Input value={newGroupName} onChange={(event) => setNewGroupName(event.target.value)} placeholder="Character glossary" />
                                        <Button type="button" className="w-full" onClick={addLabelGroup} disabled={newGroupName.trim().length === 0}>
                                            Add Label Group
                                        </Button>
                                    </div>

                                    <div className="space-y-3 rounded-lg border border-black/10 bg-slate-50 p-3">
                                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Active group</div>
                                        {activeGroupView ? (
                                            <>
                                                <div className="text-sm font-medium text-slate-900">{activeGroupView.labelGroupName}</div>
                                                <div className="grid grid-cols-2 gap-2">
                                                    <Button type="button" variant="secondary" onClick={() => addLabelFromSelection()} disabled={!canOperateOnSelection}>
                                                        Add Selection
                                                    </Button>
                                                    <Button type="button" variant="secondary" onClick={() => updateLabelFromSelection(selectedLabel)} disabled={!selectedLabel || !canOperateOnSelection}>
                                                        Update Label
                                                    </Button>
                                                    <Button type="button" variant="outline" onClick={() => deleteLabelRef(selectedLabel)} disabled={!selectedLabel || !(selectedLabel.role === "editor" || selectedLabel.role === "owner")}>
                                                        Delete Label
                                                    </Button>
                                                    <Button type="button" variant="outline" onClick={() => setSelectedLabelRef(null)} disabled={!selectedLabel}>
                                                        Clear
                                                    </Button>
                                                </div>
                                            </>
                                        ) : (
                                            <p className="text-sm text-slate-500">Choose a label group to start labeling.</p>
                                        )}
                                    </div>

                                    <div className="space-y-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Labels in active group</div>
                                        <div className="max-h-72 space-y-2 overflow-auto pr-1">
                                            {activeLabels.length > 0 ? activeLabels.map((label) => {
                                                const isSelected = selectedLabelRef?.labelGroupId === activeGroupId && selectedLabelRef.labelId === label.labelId;
                                                return (
                                                    <button
                                                        key={label.labelId}
                                                        type="button"
                                                        onClick={() => activeGroupId ? setSelectedLabelRef({ labelGroupId: activeGroupId, labelId: label.labelId }) : undefined}
                                                        className={`w-full rounded-lg border px-3 py-3 text-left transition ${isSelected ? "border-amber-400 bg-amber-50" : "border-black/10 bg-white hover:border-amber-300"}`}
                                                    >
                                                        <div className="flex items-start justify-between gap-3">
                                                            <div>
                                                                <div className="text-sm font-medium text-slate-900">{label.labelWord}</div>
                                                                <div className="mt-1 text-xs text-slate-500">
                                                                    [{label.labelStart}, {label.labelEnd}) {label.labelEntityGroup ? `- ${label.labelEntityGroup}` : ""}
                                                                </div>
                                                            </div>
                                                            <LabelStateBadge label={label} />
                                                        </div>
                                                    </button>
                                                );
                                            }) : (
                                                <div className="rounded-lg border border-dashed border-black/10 bg-white px-4 py-4 text-sm text-slate-500">
                                                    {activeGroupView ? "No labels in this group yet." : "No active label group selected."}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </TabsContent>

                                <TabsContent value="chapters" className="space-y-4 pt-3">
                                    <div className="max-h-72 space-y-2 overflow-auto pr-1">
                                        {chapterList.map((chapter) => (
                                            <button
                                                key={chapter.chapterId}
                                                type="button"
                                                onClick={() => onSelectChapter(chapter.chapterId)}
                                                className={`flex w-full flex-col rounded-lg border px-3 py-3 text-left ${chapter.chapterId === editChapterData.chapter.chapterId ? "border-amber-400 bg-amber-50" : "border-black/10 bg-white"}`}
                                            >
                                                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Chapter {chapter.chapterNum}</span>
                                                <span className="mt-1 text-sm font-medium text-slate-900">{chapter.chapterTitle || `Chapter ${chapter.chapterNum}`}</span>
                                            </button>
                                        ))}
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
                                </TabsContent>

                                <TabsContent value="future" className="space-y-3 pt-3">
                                    <div className="rounded-lg border border-dashed border-black/10 bg-slate-50 p-4 text-sm text-slate-500">Auto-labels panel placeholder.</div>
                                    <div className="rounded-lg border border-dashed border-black/10 bg-slate-50 p-4 text-sm text-slate-500">Filters panel placeholder.</div>
                                </TabsContent>
                            </Tabs>
                        </CardContent>
                    </Card>
                </aside>
            </div>

            {labelPopup ? (
                <div
                    data-label-popup
                    className="fixed z-50 w-80 rounded-lg border border-black/10 bg-white p-3 text-sm shadow-[0_18px_50px_rgba(15,23,42,0.22)]"
                    style={{ left: clamp(labelPopup.x + 12, 12, window.innerWidth - 340), top: clamp(labelPopup.y + 12, 12, window.innerHeight - 360) }}
                >
                    {labelPopup.type === "selection" ? (
                        <div className="space-y-3">
                            <div className="font-semibold text-slate-950">Add label</div>
                            <select
                                value={popupGroupId ?? ""}
                                onChange={(event) => switchLabelGroup(event.target.value || null)}
                                className="w-full rounded-md border border-black/10 bg-white px-3 py-2"
                            >
                                {labelGroupViews.map((group) => (
                                    <option key={group.labelGroupId} value={group.labelGroupId}>{group.labelGroupName}</option>
                                ))}
                            </select>
                            <Input value={labelEntityGroup} onChange={(event) => setLabelEntityGroup(event.target.value)} placeholder="Entity group" />
                            <Input value={labelScore} onChange={(event) => setLabelScore(event.target.value)} placeholder="Score" />
                            <label className="flex items-center gap-2 text-sm text-slate-700">
                                <input type="checkbox" checked={labelDirty} onChange={(event) => setLabelDirty(event.target.checked)} />
                                Mark dirty
                            </label>
                            <div className="flex gap-2">
                                <Button type="button" className="flex-1" onClick={() => addLabelFromSelection(popupGroupId ?? undefined)} disabled={!popupGroupId}>
                                    Add
                                </Button>
                                <Button type="button" variant="outline" onClick={() => setLabelPopup(null)}>Cancel</Button>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <div className="font-semibold text-slate-950">Labels at cursor</div>
                            <select
                                value={labelPopup.selectedIndex}
                                onChange={(event) => {
                                    const selectedIndex = Number(event.target.value);
                                    setLabelPopup({ ...labelPopup, selectedIndex });
                                    const selected = labelPopup.candidates[selectedIndex];
                                    if (selected) {
                                        setSelectedLabelRef(selected);
                                        switchLabelGroup(selected.labelGroupId);
                                    }
                                }}
                                className="w-full rounded-md border border-black/10 bg-white px-3 py-2"
                            >
                                {clickedPopupLabels.map((candidate, index) => (
                                    <option key={`${candidate.labelGroupId}:${candidate.label.labelId}`} value={index}>
                                        {candidate.labelGroupName}: {candidate.label.labelWord}
                                    </option>
                                ))}
                            </select>
                            {clickedPopupLabel ? (
                                <>
                                    <div className="rounded-md border border-black/10 bg-slate-50 p-3">
                                        <div className="font-medium text-slate-900">{clickedPopupLabel.label.labelWord}</div>
                                        <div className="mt-1 text-xs text-slate-500">[{clickedPopupLabel.label.labelStart}, {clickedPopupLabel.label.labelEnd})</div>
                                        <div className="mt-1 text-xs text-slate-500">{clickedPopupLabel.label.labelEntityGroup || "No entity group"}</div>
                                    </div>
                                    <Input value={labelEntityGroup} onChange={(event) => setLabelEntityGroup(event.target.value)} placeholder="Entity group" />
                                    <Input value={labelScore} onChange={(event) => setLabelScore(event.target.value)} placeholder="Score" />
                                    <label className="flex items-center gap-2 text-sm text-slate-700">
                                        <input type="checkbox" checked={labelDirty} onChange={(event) => setLabelDirty(event.target.checked)} />
                                        Mark dirty
                                    </label>
                                    <div className="grid grid-cols-2 gap-2">
                                        <Button type="button" variant="secondary" onClick={() => updateLabelFromSelection(clickedPopupLabel)} disabled={selection.start >= selection.end}>
                                            Use Selection
                                        </Button>
                                        <Button type="button" variant="outline" onClick={() => deleteLabelRef(clickedPopupLabel)}>
                                            Delete
                                        </Button>
                                    </div>
                                </>
                            ) : null}
                        </div>
                    )}
                </div>
            ) : null}
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

    const [currentUser, currentUserLoading, currentUserError, reloadCurrentUser] = useLoader<User | null>(
        null,
        loadCurrentUser,
        [],
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
            reloadCurrentUser(),
        ]);
    }, [reloadChapterList, reloadCurrentUser, reloadEditChapterData, reloadNovel]);

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

    const loadingBaseState = novelLoading
        || chapterListLoading
        || currentUserLoading
        || (Boolean(chapterId) && !editChapterData && editChapterDataLoading);
    const topLevelError = novelError ?? chapterListError ?? currentUserError;

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

    if (!novel || !editChapterData || !currentUser) {
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
            currentUser={currentUser}
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
