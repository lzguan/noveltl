import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
    getNovelById, updateNovel,
    getChaptersByNovel, createChapterForNovel,
    getChapterRevisionsByChapter, createRevisionForChapter,
    getRevisionText,
    publishRevision, makeRevisionPrimary, deleteRevision,
} from "../api/novels";
import { getLabelGroupsByNovel, getLabelDatas, getLabelsByLabelData, updateLabelDataStream, createLabelDataForGroup, createLabelDataByAutoLabel } from "../api/labels";
import { getAutoLabels, getAutoLabelById, createAutoLabels } from "../api/autolabels";
import { type Novel, type Chapter, type Revision, type RevisionText, type Visibility, type NovelType as NovelTypeEnum } from "../types/novel";
import { type LabelGroup, type LabelData, type Label, type LabelOp, type AddLabelOp, type CreateLabelDataByAutoLabelStatus } from "../types/label";
import { type AutoLabelMeta, type AutoLabel } from "../types/autolabel";
import { type LabelSourceConfig, applyOpToLabels } from "../components/workspace/labelOps";
import { SelectorsBar } from "../components/workspace/SelectorsBar";
import { ChapterTextViewer } from "../components/workspace/ChapterTextViewer";
import { AnnotatedText } from "../components/workspace/AnnotatedText";
import { LabelPopover } from "../components/workspace/LabelPopover";
import { NewLabelPopover } from "../components/workspace/NewLabelPopover";
import { RightPanel } from "../components/workspace/RightPanel";
import { LabelsPanel } from "../components/workspace/LabelsPanel";
import { NerPanel } from "../components/workspace/NerPanel";
import { LabelGroupSelector } from "../components/workspace/LabelGroupSelector";

type ActivePopover =
    | { type: "edit"; label: Label; rect: DOMRect }
    | { type: "new"; startPos: number; endPos: number; text: string; rect: DOMRect }
    | null;

type WorkspaceMode = "edit" | "label";

const TOP_TABS = [{ key: "novel", label: "Novel" }];
const EDIT_TABS = [{ key: "editor", label: "Editor" }, { key: "editLabels", label: "Labels" }];
const LABEL_TABS = [{ key: "labels", label: "Labels" }, { key: "ner", label: "NER" }, { key: "filters", label: "Filters" }];

export const NovelWorkspacePage = () => {
    const { novel_id } = useParams<{ novel_id: string }>();
    const [searchParams, setSearchParams] = useSearchParams();
    const textContainerRef = useRef<HTMLDivElement>(null);

    // Mode
    const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>("label");
    const modeTabs = workspaceMode === "edit" ? EDIT_TABS : LABEL_TABS;

    // Core data
    const [novel, setNovel] = useState<Novel | null>(null);
    const [chapters, setChapters] = useState<Chapter[]>([]);
    const [labelGroups, setLabelGroups] = useState<LabelGroup[]>([]);

    // Selection state
    const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
    const [chapterRevisions, setChapterRevisions] = useState<Revision[]>([]);
    const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(null);
    const [revisionText, setRevisionText] = useState<string | null>(null);
    const [revisionTextId, setRevisionTextId] = useState<string | null>(null);

    // Per-tab label group state
    const [labelsTabGroupId, setLabelsTabGroupId] = useState<string | null>(null);
    const [labelsTabLabelData, setLabelsTabLabelData] = useState<LabelData | null>(null);
    const [labelsTabLabels, setLabelsTabLabels] = useState<Label[]>([]);

    const [nerTabGroupId, setNerTabGroupId] = useState<string | null>(null);
    const [, setNerTabLabelData] = useState<LabelData | null>(null);
    const [nerTabLabels, setNerTabLabels] = useState<Label[]>([]);

    const [filtersTabGroupId, setFiltersTabGroupId] = useState<string | null>(null);

    // Popover state
    const [activePopover, setActivePopover] = useState<ActivePopover>(null);
    const [pendingOpError, setPendingOpError] = useState<string | null>(null);

    // Right panel state
    const [activeRightPanel, setActiveRightPanel] = useState("labels");
    const [scoreThreshold, setScoreThreshold] = useState(0);
    const [entityGroupFilter, setEntityGroupFilter] = useState<Set<string>>(new Set());
    const [sortBy, setSortBy] = useState<"position" | "score" | "entityGroup" | "word">("position");
    const [searchWord, setSearchWord] = useState("");
    const [highlightedLabelId, setHighlightedLabelId] = useState<string | null>(null);

    // NER state
    const [autoLabelMetas, setAutoLabelMetas] = useState<AutoLabelMeta[]>([]);
    const [selectedAutoLabelId, setSelectedAutoLabelId] = useState<string | null>(null);
    const [autoLabelPreview, setAutoLabelPreview] = useState<AutoLabel | null>(null);
    const [showAutoLabelPreview, setShowAutoLabelPreview] = useState(false);
    const [nerModelName, setNerModelName] = useState("");
    const [nerModelParams, setNerModelParams] = useState("{}");
    const [isRunningNer, setIsRunningNer] = useState(false);
    const [loadStatus, setLoadStatus] = useState<CreateLabelDataByAutoLabelStatus | null>(null);

    // Novel metadata form state
    const [novelTitle, setNovelTitle] = useState("");
    const [novelDescription, setNovelDescription] = useState("");
    const [novelAuthor, setNovelAuthor] = useState("");
    const [novelVisibility, setNovelVisibility] = useState<Visibility>(0);
    const [novelType, setNovelType] = useState<NovelTypeEnum>("original");
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);

    // Editor tab state — newChapterNum defaults to max+1 once chapters load
    const [newChapterNum, setNewChapterNum] = useState("");
    const [newRevisionTitle, setNewRevisionTitle] = useState("");
    // newRevisionText removed — text editing happens inline once edit mode is toggled

    // Loading/error
    const [loading, setLoading] = useState(true);
    const [textLoading, setTextLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Derived: next chapter number
    const nextChapterNum = useMemo(() => {
        if (chapters.length === 0) return 1;
        return Math.max(...chapters.map((c) => c.chapterNum)) + 1;
    }, [chapters]);

    // Derived: known entity groups from labels-tab labels
    const knownEntityGroups = useMemo(() => {
        const groups = new Set<string>();
        for (const l of labelsTabLabels) {
            if (l.labelEntityGroup) groups.add(l.labelEntityGroup);
        }
        return [...groups].sort();
    }, [labelsTabLabels]);

    // Derived: auto-label metas filtered to current revision text
    const filteredAutoLabelMetas = useMemo(
        () => revisionTextId ? autoLabelMetas.filter((m) => m.revisionTextId === revisionTextId) : [],
        [autoLabelMetas, revisionTextId]
    );

    // Derived: currently selected auto-label meta (from filtered set)
    const autoLabelMeta = useMemo(
        () => filteredAutoLabelMetas.find((m) => m.autoLabelId === selectedAutoLabelId) ?? null,
        [filteredAutoLabelMetas, selectedAutoLabelId]
    );

    // Shared fetch helper for loading labels for a group
    const loadLabelsForGroup = useCallback(async (
        groupId: string | null,
        currentRevisionTextId: string | null,
        setLabelData: React.Dispatch<React.SetStateAction<LabelData | null>>,
        setLabels: React.Dispatch<React.SetStateAction<Label[]>>,
    ) => {
        if (!groupId || !currentRevisionTextId) {
            setLabelData(null);
            setLabels([]);
            return;
        }
        try {
            const allLabelDatas = await getLabelDatas(groupId);
            const match = allLabelDatas.find((ld) => ld.revisionTextId === currentRevisionTextId);
            if (!match) {
                setLabelData(null);
                setLabels([]);
                return;
            }
            setLabelData(match);
            const fetchedLabels = await getLabelsByLabelData(match.labelDataId);
            setLabels(fetchedLabels);
        } catch {
            setLabelData(null);
            setLabels([]);
        }
    }, []);

    const populateNovelForm = (n: Novel) => {
        setNovelTitle(n.novelTitle);
        setNovelDescription(n.novelDescription ?? "");
        setNovelAuthor(n.novelAuthor ?? "");
        setNovelVisibility(n.novelVisibility);
        setNovelType(n.novelType);
    };

    // Sync query params → state on mount
    const initFromParams = useCallback(() => {
        const chapter = searchParams.get("chapter");
        const revision = searchParams.get("revision");
        const labelsGroup = searchParams.get("labelsGroup");
        const nerGroup = searchParams.get("nerGroup");
        if (chapter) setSelectedChapterId(chapter);
        if (revision) setSelectedRevisionId(revision);
        if (labelsGroup) setLabelsTabGroupId(labelsGroup);
        if (nerGroup) setNerTabGroupId(nerGroup);
    }, [searchParams]);

    // Fetch novel, chapters, label groups on mount
    useEffect(() => {
        if (!novel_id) return;
        setLoading(true);
        setError(null);

        Promise.all([
            getNovelById(novel_id),
            getChaptersByNovel(novel_id),
            getLabelGroupsByNovel(novel_id),
        ])
            .then(([fetchedNovel, fetchedChapters, fetchedGroups]) => {
                setNovel(fetchedNovel);
                setChapters(fetchedChapters);
                setLabelGroups(fetchedGroups);
                populateNovelForm(fetchedNovel);
                initFromParams();
            })
            .catch(() => setError("Failed to load workspace data"))
            .finally(() => setLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [novel_id]);

    // Fetch revisions when chapter changes + auto-select
    useEffect(() => {
        if (!selectedChapterId) {
            setChapterRevisions([]);
            return;
        }
        getChapterRevisionsByChapter(selectedChapterId)
            .then((revisions) => {
                setChapterRevisions(revisions);
                const primary = revisions.find((r) => r.revisionIsPrimary);
                const latest = revisions.length > 0 ? revisions[revisions.length - 1] : null;
                const autoSelect = primary ?? latest;
                if (autoSelect) setSelectedRevisionId(autoSelect.revisionId);
            })
            .catch(() => setChapterRevisions([]));
    }, [selectedChapterId]);

    // Fetch revision text when revision changes
    useEffect(() => {
        if (!selectedRevisionId) {
            setRevisionText(null);
            setRevisionTextId(null);
            return;
        }
        setTextLoading(true);
        getRevisionText(selectedRevisionId)
            .then((rt: RevisionText) => {
                setRevisionText(rt.revisionTextContent);
                setRevisionTextId(rt.revisionTextId);
            })
            .catch(() => {
                setRevisionText(null);
                setRevisionTextId(null);
            })
            .finally(() => setTextLoading(false));
    }, [selectedRevisionId]);

    // Fetch labels for labels-tab group
    useEffect(() => {
        void loadLabelsForGroup(labelsTabGroupId, revisionTextId, setLabelsTabLabelData, setLabelsTabLabels);
    }, [labelsTabGroupId, revisionTextId, loadLabelsForGroup]);

    // Fetch labels for NER-tab group
    useEffect(() => {
        void loadLabelsForGroup(nerTabGroupId, revisionTextId, setNerTabLabelData, setNerTabLabels);
    }, [nerTabGroupId, revisionTextId, loadLabelsForGroup]);

    // Fetch auto-label metas when revision changes
    useEffect(() => {
        if (!selectedRevisionId || !novel) {
            setAutoLabelMetas([]);
            setSelectedAutoLabelId(null);
            setAutoLabelPreview(null);
            setShowAutoLabelPreview(false);
            setLoadStatus(null);
            return;
        }
        getAutoLabels(novel.novelId, null, [selectedRevisionId])
            .then((metas) => {
                setAutoLabelMetas(metas);
                // Auto-select is handled reactively via filteredAutoLabelMetas effect
            })
            .catch(() => {
                setAutoLabelMetas([]);
                setSelectedAutoLabelId(null);
            });
    }, [selectedRevisionId, novel]);

    // Auto-select first NER run when filtered list changes
    useEffect(() => {
        if (filteredAutoLabelMetas.length > 0) {
            const current = filteredAutoLabelMetas.find((m) => m.autoLabelId === selectedAutoLabelId);
            if (!current) setSelectedAutoLabelId(filteredAutoLabelMetas[0].autoLabelId);
        } else {
            setSelectedAutoLabelId(null);
        }
    }, [filteredAutoLabelMetas, selectedAutoLabelId]);

    // Poll auto-label status when pending/processing
    useEffect(() => {
        if (!autoLabelMeta || !novel) return;
        const status = autoLabelMeta.autoLabelStatus;
        if (status !== "pending" && status !== "processing") return;

        const interval = setInterval(() => {
            if (!selectedRevisionId) return;
            getAutoLabels(novel.novelId, null, [selectedRevisionId])
                .then((metas) => {
                    setAutoLabelMetas(metas);
                    const updated = metas.find((m) => m.autoLabelId === autoLabelMeta.autoLabelId);
                    if (updated && updated.autoLabelStatus !== "pending" && updated.autoLabelStatus !== "processing") {
                        clearInterval(interval);
                    }
                })
                .catch(() => { /* keep polling */ });
        }, 3000);

        return () => clearInterval(interval);
    }, [autoLabelMeta?.autoLabelStatus, autoLabelMeta?.autoLabelId, novel, selectedRevisionId]);

    // Sync state → query params
    useEffect(() => {
        const params = new URLSearchParams();
        if (selectedChapterId) params.set("chapter", selectedChapterId);
        if (selectedRevisionId) params.set("revision", selectedRevisionId);
        if (labelsTabGroupId) params.set("labelsGroup", labelsTabGroupId);
        if (nerTabGroupId) params.set("nerGroup", nerTabGroupId);
        setSearchParams(params, { replace: true });
    }, [selectedChapterId, selectedRevisionId, labelsTabGroupId, nerTabGroupId, setSearchParams]);

    // Ensure labelsTab labelData exists, creating it if needed
    const ensureLabelData = useCallback(async (): Promise<LabelData | null> => {
        if (labelsTabLabelData) return labelsTabLabelData;
        if (!labelsTabGroupId || !revisionTextId) return null;
        const created = await createLabelDataForGroup(labelsTabGroupId, { revisionTextId });
        setLabelsTabLabelData(created);
        return created;
    }, [labelsTabLabelData, labelsTabGroupId, revisionTextId]);

    // Optimistic label operation handler (operates on labels tab)
    const handleLabelOp = useCallback(async (op: LabelOp) => {
        const ld = await ensureLabelData();
        if (!ld) return;
        const snapshot = labelsTabLabels;
        setLabelsTabLabels((prev) => applyOpToLabels(prev, op));
        setActivePopover(null);
        setPendingOpError(null);
        try {
            await updateLabelDataStream(ld.labelDataId, { ops: [op] });
        } catch {
            setLabelsTabLabels(snapshot);
            setPendingOpError("Failed to save label change. Reverted.");
        }
    }, [ensureLabelData, labelsTabLabels]);

    const handleModeChange = (mode: WorkspaceMode) => {
        setWorkspaceMode(mode);
        // Novel is top-level now; when switching modes, reset to first mode-specific tab
        // unless the user is already on the novel tab
        if (activeRightPanel !== "novel") {
            setActiveRightPanel(mode === "edit" ? "editor" : "labels");
        }
    };

    const handleChapterChange = (chapterId: string | null) => {
        setSelectedChapterId(chapterId);
        setRevisionText(null);
        setRevisionTextId(null);
        setChapterRevisions([]);
        // selectedRevisionId will be set by the useEffect that fetches revisions
    };

    const handleRevisionChange = (revisionId: string | null) => {
        setSelectedRevisionId(revisionId);
        if (!revisionId) {
            setRevisionText(null);
            setRevisionTextId(null);
        }
    };

    const handleLabelGroupCreated = (labelGroup: LabelGroup) => {
        setLabelGroups((prev) => [...prev, labelGroup]);
        setLabelsTabGroupId(labelGroup.labelGroupId);
    };

    const handleLabelClick = (label: Label, rect: DOMRect) => {
        if (workspaceMode === "edit") return;
        setActivePopover({ type: "edit", label, rect });
    };

    const handleTextSelect = (selection: { startPos: number; endPos: number; text: string; rect: DOMRect }) => {
        if (workspaceMode === "edit") return;
        if (activeRightPanel !== "labels" || !labelsTabGroupId) return;
        setActivePopover({ type: "new", ...selection });
    };

    const handleNewLabelConfirm = (op: AddLabelOp) => {
        void handleLabelOp(op);
    };

    const handleEntityGroupFilterToggle = (group: string) => {
        setEntityGroupFilter((prev) => {
            const next = new Set(prev);
            if (next.has(group)) {
                next.delete(group);
            } else {
                next.add(group);
            }
            return next;
        });
    };

    const handleScrollToLabel = (label: Label) => {
        const container = textContainerRef.current;
        if (!container) return;
        const span = container.querySelector(`[data-label-start="${label.labelStart}"][data-label-end="${label.labelEnd}"]`);
        if (span) {
            span.scrollIntoView({ behavior: "smooth", block: "center" });
            const key = `${label.labelStart}-${label.labelEnd}`;
            setHighlightedLabelId(key);
            setTimeout(() => setHighlightedLabelId(null), 1500);
        }
    };

    const handleRunNer = async () => {
        if (!novel || !selectedRevisionId) return;
        setIsRunningNer(true);
        try {
            let parsedParams = {};
            try { parsedParams = JSON.parse(nerModelParams); } catch { /* use empty */ }
            const results = await createAutoLabels({
                novelId: novel.novelId,
                autoLabelModelName: nerModelName.trim(),
                autoLabelModelParams: parsedParams,
                revisionIds: [selectedRevisionId],
            });
            if (results.length > 0) {
                setAutoLabelMetas((prev) => [...prev, ...results]);
                setSelectedAutoLabelId(results[0].autoLabelId);
            }
        } catch {
            setPendingOpError("Failed to start NER.");
        } finally {
            setIsRunningNer(false);
        }
    };

    const handleTogglePreview = async (show: boolean) => {
        setShowAutoLabelPreview(show);
        if (show && autoLabelMeta) {
            if (!autoLabelPreview || autoLabelPreview.autoLabelId !== autoLabelMeta.autoLabelId) {
                try {
                    const full = await getAutoLabelById(autoLabelMeta.autoLabelId);
                    setAutoLabelPreview(full);
                } catch {
                    setShowAutoLabelPreview(false);
                }
            }
        }
    };

    const handleAutoLabelSelect = (autoLabelId: string) => {
        setSelectedAutoLabelId(autoLabelId);
        setAutoLabelPreview(null);
        setShowAutoLabelPreview(false);
        setLoadStatus(null);
    };

    const handleLoadIntoGroup = async () => {
        if (!nerTabGroupId || !autoLabelMeta) return;
        try {
            const status = await createLabelDataByAutoLabel(nerTabGroupId, {
                modelName: autoLabelMeta.autoLabelModelName,
                modelParams: autoLabelMeta.autoLabelModelParams,
                revisionIds: [selectedRevisionId!],
            });
            setLoadStatus(status);
            // Reload NER-tab labels after loading
            await loadLabelsForGroup(nerTabGroupId, revisionTextId, setNerTabLabelData, setNerTabLabels);
            // Also reload labels-tab if same group
            if (labelsTabGroupId === nerTabGroupId) {
                await loadLabelsForGroup(labelsTabGroupId, revisionTextId, setLabelsTabLabelData, setLabelsTabLabels);
            }
        } catch {
            setPendingOpError("Failed to load NER results into group.");
        }
    };

    // Novel metadata handlers
    const handleSaveNovel = async () => {
        if (!novel) return;
        setSaving(true);
        setSaveMessage(null);
        try {
            const updated = await updateNovel(novel.novelId, {
                novelTitle,
                novelDescription: novelDescription || undefined,
                novelAuthor: novelAuthor || undefined,
                novelVisibility,
                novelType,
            });
            setNovel(updated);
            setSaveMessage("Saved successfully.");
        } catch {
            setSaveMessage("Failed to save.");
        } finally {
            setSaving(false);
        }
    };

    // Editor tab handlers
    const handleCreateChapter = async () => {
        if (!novel) return;
        const num = newChapterNum.trim() ? Number(newChapterNum) : nextChapterNum;
        try {
            const created = await createChapterForNovel(novel.novelId, {
                chapterNum: num,
            });
            setChapters((prev) => [...prev, created]);
            setNewChapterNum("");
            handleChapterChange(created.chapterId);
        } catch {
            setSaveMessage("Failed to create chapter.");
        }
    };

    const handleCreateRevision = async () => {
        if (!selectedChapterId || !newRevisionTitle.trim()) return;
        try {
            const result = await createRevisionForChapter(selectedChapterId, {
                revisionTitle: newRevisionTitle,
            });
            const revisions = await getChapterRevisionsByChapter(selectedChapterId);
            setChapterRevisions(revisions);
            // Auto-select the newly created revision
            setSelectedRevisionId(result.metadata.revisionId);
            setNewRevisionTitle("");
        } catch {
            setSaveMessage("Failed to create revision.");
        }
    };

    const handleRevisionAction = async (action: "publish" | "primary" | "delete", revisionId: string) => {
        if (action === "delete" && !window.confirm("Delete this revision?")) return;
        try {
            if (action === "publish") await publishRevision(revisionId);
            else if (action === "primary") await makeRevisionPrimary(revisionId);
            else if (action === "delete") await deleteRevision(revisionId);

            if (selectedChapterId) {
                const revisions = await getChapterRevisionsByChapter(selectedChapterId);
                setChapterRevisions(revisions);
                if (action === "delete" && selectedRevisionId === revisionId) {
                    setSelectedRevisionId(null);
                    setRevisionText(null);
                    setRevisionTextId(null);
                }
            }
        } catch {
            setSaveMessage(`Failed to ${action} revision.`);
        }
    };

    // Build label sources for multi-layer rendering
    const sources = useMemo((): LabelSourceConfig[] => {
        const result: LabelSourceConfig[] = [];
        const nerPreviewLabels = showAutoLabelPreview && autoLabelPreview?.autoLabelData
            ? autoLabelPreview.autoLabelData : null;

        // Dedup: if two tabs select the same group, only show it once as bright
        const nerTabIsSameAsLabelsTab = nerTabGroupId !== null && nerTabGroupId === labelsTabGroupId;

        if (activeRightPanel === "labels" || activeRightPanel === "editLabels") {
            if (labelsTabGroupId !== null && labelsTabLabels.length > 0) {
                result.push({
                    sourceKey: "labelsTab",
                    labels: labelsTabLabels,
                    style: "bright",
                    mode: "highlight",
                    interactive: activeRightPanel === "labels",
                    priority: 0,
                });
            }
            if (!nerTabIsSameAsLabelsTab && nerTabGroupId !== null && nerTabLabels.length > 0) {
                result.push({
                    sourceKey: "nerTabGroup",
                    labels: nerTabLabels,
                    style: "dim",
                    mode: "underline",
                    interactive: false,
                    priority: 1,
                });
            }
        } else if (activeRightPanel === "ner") {
            if (nerPreviewLabels && nerPreviewLabels.length > 0) {
                result.push({
                    sourceKey: "nerResults",
                    labels: nerPreviewLabels,
                    style: "bright",
                    mode: "highlight",
                    interactive: false,
                    priority: 0,
                });
            }
            if (nerTabGroupId !== null && nerTabLabels.length > 0) {
                result.push({
                    sourceKey: "nerTabGroup",
                    labels: nerTabLabels,
                    style: "bright",
                    mode: "highlight",
                    interactive: true,
                    priority: nerPreviewLabels ? 1 : 0,
                });
            }
            if (!nerTabIsSameAsLabelsTab && labelsTabGroupId !== null && labelsTabLabels.length > 0) {
                result.push({
                    sourceKey: "labelsTab",
                    labels: labelsTabLabels,
                    style: "dim",
                    mode: "underline",
                    interactive: false,
                    priority: 2,
                });
            }
        } else if (activeRightPanel === "filters") {
            if (labelsTabGroupId !== null && labelsTabLabels.length > 0) {
                result.push({
                    sourceKey: "labelsTab",
                    labels: labelsTabLabels,
                    style: "dim",
                    mode: "underline",
                    interactive: false,
                    priority: 1,
                });
            }
            if (nerTabGroupId !== null && nerTabLabels.length > 0 && nerTabGroupId !== labelsTabGroupId) {
                result.push({
                    sourceKey: "nerTabGroup",
                    labels: nerTabLabels,
                    style: "dim",
                    mode: "underline",
                    interactive: false,
                    priority: 2,
                });
            }
        }

        return result;
    }, [
        activeRightPanel, labelsTabGroupId, labelsTabLabels, nerTabGroupId, nerTabLabels,
        showAutoLabelPreview, autoLabelPreview,
    ]);

    if (loading) return <div style={{ padding: "20px" }}>Loading workspace...</div>;
    if (error) return <div style={{ padding: "20px", color: "red" }}>{error}</div>;
    if (!novel) return <div style={{ padding: "20px" }}>Novel not found.</div>;

    const showAnnotated = revisionText !== null && (
        sources.length > 0 || labelsTabGroupId !== null || nerTabGroupId !== null
    );

    const sortedChapters = [...chapters].sort((a, b) => a.chapterNum - b.chapterNum);

    return (
        <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 60px)" }}>
            <SelectorsBar
                novel={novel}
                chapters={chapters}
                selectedChapterId={selectedChapterId}
                onChapterChange={handleChapterChange}
                chapterRevisions={chapterRevisions}
                selectedRevisionId={selectedRevisionId}
                onRevisionChange={handleRevisionChange}
                mode={workspaceMode}
                onModeChange={handleModeChange}
            />
            {pendingOpError && (
                <div style={{ padding: "6px 16px", backgroundColor: "#fee", color: "red", fontSize: "0.85rem" }}>
                    {pendingOpError}
                </div>
            )}
            {saveMessage && (
                <div style={{ padding: "6px 16px", backgroundColor: saveMessage.includes("Failed") ? "#fee" : "#efe", color: saveMessage.includes("Failed") ? "red" : "green", fontSize: "0.85rem" }}>
                    {saveMessage}
                </div>
            )}
            <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
                <div ref={textContainerRef} style={{ flex: 1, overflow: "auto" }}>
                    {showAnnotated ? (
                        <AnnotatedText
                            text={revisionText}
                            sources={sources}
                            highlightedLabelId={highlightedLabelId}
                            onLabelClick={handleLabelClick}
                            onTextSelect={handleTextSelect}
                        />
                    ) : (
                        <ChapterTextViewer text={revisionText} loading={textLoading} />
                    )}
                </div>
                <div style={{ width: "380px", flexShrink: 0 }}>
                    <RightPanel topTabs={TOP_TABS} tabs={modeTabs} activeTab={activeRightPanel} onTabChange={setActiveRightPanel}>
                        {/* Novel tab — always available */}
                        {activeRightPanel === "novel" && (
                            <div style={{ padding: "12px", display: "flex", flexDirection: "column", gap: "10px" }}>
                                <label style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.85rem" }}>
                                    Title
                                    <input value={novelTitle} onChange={(e) => setNovelTitle(e.target.value)} />
                                </label>
                                <label style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.85rem" }}>
                                    Description
                                    <textarea rows={3} value={novelDescription} onChange={(e) => setNovelDescription(e.target.value)} />
                                </label>
                                <label style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.85rem" }}>
                                    Author
                                    <input value={novelAuthor} onChange={(e) => setNovelAuthor(e.target.value)} />
                                </label>
                                <label style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.85rem" }}>
                                    Visibility
                                    <select value={novelVisibility} onChange={(e) => setNovelVisibility(Number(e.target.value) as Visibility)}>
                                        <option value={0}>Private</option>
                                        <option value={1}>Restricted</option>
                                        <option value={2}>Unlisted</option>
                                        <option value={3}>Public</option>
                                    </select>
                                </label>
                                <label style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.85rem" }}>
                                    Type
                                    <select value={novelType} onChange={(e) => setNovelType(e.target.value as NovelTypeEnum)}>
                                        <option value="original">Original</option>
                                        <option value="translation">Translation</option>
                                        <option value="other">Other</option>
                                    </select>
                                </label>
                                <label style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "0.85rem" }}>
                                    Language
                                    <input value={novel.languageCode} disabled style={{ backgroundColor: "#eee" }} />
                                </label>
                                <button onClick={() => void handleSaveNovel()} disabled={saving}>
                                    {saving ? "Saving..." : "Save"}
                                </button>
                            </div>
                        )}

                        {/* Editor tab — edit mode only */}
                        {activeRightPanel === "editor" && (
                            <div style={{ padding: "12px" }}>
                                {/* Chapter list */}
                                <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px" }}>
                                    {sortedChapters.map((ch) => (
                                        <button
                                            key={ch.chapterId}
                                            onClick={() => handleChapterChange(ch.chapterId)}
                                            style={{
                                                padding: "6px 10px",
                                                textAlign: "left",
                                                border: "1px solid #ddd",
                                                borderRadius: "4px",
                                                backgroundColor: selectedChapterId === ch.chapterId ? "#e3f0ff" : "#fff",
                                                fontWeight: selectedChapterId === ch.chapterId ? 600 : 400,
                                                cursor: "pointer",
                                            }}
                                        >
                                            Ch. {ch.chapterNum}
                                        </button>
                                    ))}
                                    {sortedChapters.length === 0 && (
                                        <div style={{ color: "#999", fontSize: "0.85rem" }}>No chapters yet.</div>
                                    )}
                                </div>
                                <div style={{ borderTop: "1px solid #ddd", paddingTop: "10px", display: "flex", gap: "6px", alignItems: "center" }}>
                                    <input
                                        type="number"
                                        placeholder={String(nextChapterNum)}
                                        value={newChapterNum}
                                        onChange={(e) => setNewChapterNum(e.target.value)}
                                        style={{ width: "80px", padding: "4px" }}
                                    />
                                    <button onClick={() => void handleCreateChapter()}>
                                        Add Chapter
                                    </button>
                                </div>

                                {/* Revision list */}
                                <div style={{ borderTop: "1px solid #ddd", marginTop: "12px", paddingTop: "12px" }}>
                                    {!selectedChapterId ? (
                                        <div style={{ color: "#999", fontSize: "0.85rem", fontStyle: "italic" }}>
                                            Select a chapter first.
                                        </div>
                                    ) : (
                                        <>
                                            <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "12px" }}>
                                                {chapterRevisions.map((rev) => (
                                                    <div
                                                        key={rev.revisionId}
                                                        style={{
                                                            padding: "8px",
                                                            border: "1px solid #ddd",
                                                            borderRadius: "4px",
                                                            backgroundColor: selectedRevisionId === rev.revisionId ? "#e3f0ff" : "#fff",
                                                        }}
                                                    >
                                                        <div
                                                            onClick={() => handleRevisionChange(rev.revisionId)}
                                                            style={{ cursor: "pointer", marginBottom: "4px", fontWeight: selectedRevisionId === rev.revisionId ? 600 : 400 }}
                                                        >
                                                            {rev.revisionTitle || `Revision ${rev.revisionId}`}
                                                            {rev.revisionIsPrimary && <span style={{ marginLeft: "6px", color: "green", fontSize: "0.75rem" }}>PRIMARY</span>}
                                                            {rev.revisionIsPublic && <span style={{ marginLeft: "6px", color: "#4a90d9", fontSize: "0.75rem" }}>PUBLIC</span>}
                                                        </div>
                                                        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                                                            <button style={{ fontSize: "0.75rem", padding: "2px 6px" }} onClick={() => void handleRevisionAction("publish", rev.revisionId)}>Publish</button>
                                                            <button style={{ fontSize: "0.75rem", padding: "2px 6px" }} onClick={() => void handleRevisionAction("primary", rev.revisionId)}>Primary</button>
                                                            <button style={{ fontSize: "0.75rem", padding: "2px 6px", color: "red" }} onClick={() => void handleRevisionAction("delete", rev.revisionId)}>Delete</button>
                                                        </div>
                                                    </div>
                                                ))}
                                                {chapterRevisions.length === 0 && (
                                                    <div style={{ color: "#999", fontSize: "0.85rem" }}>No revisions for this chapter.</div>
                                                )}
                                            </div>
                                            <div style={{ borderTop: "1px solid #ddd", paddingTop: "10px", display: "flex", flexDirection: "column", gap: "6px" }}>
                                                <input
                                                    placeholder="Revision title"
                                                    value={newRevisionTitle}
                                                    onChange={(e) => setNewRevisionTitle(e.target.value)}
                                                    style={{ padding: "4px" }}
                                                />
                                                <button onClick={() => void handleCreateRevision()} disabled={!newRevisionTitle.trim()}>
                                                    Add Revision
                                                </button>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Labels tab — edit mode (read-only) */}
                        {activeRightPanel === "editLabels" && (
                            <LabelsPanel
                                labelGroups={labelGroups}
                                selectedGroupId={labelsTabGroupId}
                                onGroupChange={setLabelsTabGroupId}
                                novelId={novel.novelId}
                                onGroupCreated={handleLabelGroupCreated}
                                labels={labelsTabLabels}
                                scoreThreshold={scoreThreshold}
                                onScoreThresholdChange={setScoreThreshold}
                                entityGroupFilter={entityGroupFilter}
                                onEntityGroupFilterToggle={handleEntityGroupFilterToggle}
                                sortBy={sortBy}
                                onSortByChange={setSortBy}
                                searchWord={searchWord}
                                onSearchWordChange={setSearchWord}
                                onLabelClick={handleScrollToLabel}
                            />
                        )}

                        {/* Labels tab — label mode (interactive) */}
                        {activeRightPanel === "labels" && (
                            <LabelsPanel
                                labelGroups={labelGroups}
                                selectedGroupId={labelsTabGroupId}
                                onGroupChange={setLabelsTabGroupId}
                                novelId={novel.novelId}
                                onGroupCreated={handleLabelGroupCreated}
                                labels={labelsTabLabels}
                                scoreThreshold={scoreThreshold}
                                onScoreThresholdChange={setScoreThreshold}
                                entityGroupFilter={entityGroupFilter}
                                onEntityGroupFilterToggle={handleEntityGroupFilterToggle}
                                sortBy={sortBy}
                                onSortByChange={setSortBy}
                                searchWord={searchWord}
                                onSearchWordChange={setSearchWord}
                                onLabelClick={handleScrollToLabel}
                            />
                        )}
                        {activeRightPanel === "ner" && (
                            <NerPanel
                                labelGroups={labelGroups}
                                selectedGroupId={nerTabGroupId}
                                onGroupChange={setNerTabGroupId}
                                autoLabelMetas={filteredAutoLabelMetas}
                                selectedAutoLabelId={selectedAutoLabelId}
                                onAutoLabelSelect={handleAutoLabelSelect}
                                autoLabelMeta={autoLabelMeta}
                                autoLabelPreview={autoLabelPreview}
                                showPreview={showAutoLabelPreview}
                                onTogglePreview={(show) => void handleTogglePreview(show)}
                                nerModelName={nerModelName}
                                onNerModelNameChange={setNerModelName}
                                nerModelParams={nerModelParams}
                                onNerModelParamsChange={setNerModelParams}
                                isRunningNer={isRunningNer}
                                onRunNer={() => void handleRunNer()}
                                onLoadIntoGroup={() => void handleLoadIntoGroup()}
                                loadStatus={loadStatus}
                            />
                        )}
                        {activeRightPanel === "filters" && (
                            <div>
                                <LabelGroupSelector
                                    labelGroups={labelGroups}
                                    selectedGroupId={filtersTabGroupId}
                                    onGroupChange={setFiltersTabGroupId}
                                />
                                <div style={{ padding: "12px", color: "#888" }}>Filters panel (deferred)</div>
                            </div>
                        )}
                    </RightPanel>
                </div>
            </div>
            {activePopover?.type === "edit" && (
                <LabelPopover
                    label={activePopover.label}
                    anchorRect={activePopover.rect}
                    knownEntityGroups={knownEntityGroups}
                    onSave={(op) => void handleLabelOp(op)}
                    onDelete={(op) => void handleLabelOp(op)}
                    onClose={() => setActivePopover(null)}
                />
            )}
            {activePopover?.type === "new" && (
                <NewLabelPopover
                    selectedText={activePopover.text}
                    startPos={activePopover.startPos}
                    endPos={activePopover.endPos}
                    anchorRect={activePopover.rect}
                    knownEntityGroups={knownEntityGroups}
                    onConfirm={handleNewLabelConfirm}
                    onClose={() => setActivePopover(null)}
                />
            )}
        </div>
    );
};
