import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { getNovelById, getChaptersByNovel, getChapterRevisionsByChapter, getChapterRevisionById } from "../api/novels";
import { getLabelGroupsByNovel, getLabelDatas, getLabelsByLabelData, updateLabelDataStream, createLabelDataForGroup, createLabelDataByAutoLabel } from "../api/labels";
import { getAutoLabels, getAutoLabelById, createAutoLabels } from "../api/autolabels";
import { type Novel, type RawChapter, type RawChapterRevisionMeta } from "../types/novel";
import { type LabelGroup, type LabelData, type Label, type LabelOp, type AddLabelOp, type CreateLabelDataByAutoLabelStatus } from "../types/label";
import { type AutoLabelMeta, type AutoLabel } from "../types/autolabel";
import { applyOpToLabels } from "../components/workspace/labelOps";
import { SelectorsBar } from "../components/workspace/SelectorsBar";
import { ChapterTextViewer } from "../components/workspace/ChapterTextViewer";
import { AnnotatedText } from "../components/workspace/AnnotatedText";
import { LabelPopover } from "../components/workspace/LabelPopover";
import { NewLabelPopover } from "../components/workspace/NewLabelPopover";
import { RightPanel } from "../components/workspace/RightPanel";
import { LabelsPanel } from "../components/workspace/LabelsPanel";
import { NerPanel } from "../components/workspace/NerPanel";

type ActivePopover =
    | { type: "edit"; label: Label; rect: DOMRect }
    | { type: "new"; startPos: number; endPos: number; text: string; rect: DOMRect }
    | null;

export const NovelWorkspacePage = () => {
    const { novel_id } = useParams<{ novel_id: string }>();
    const [searchParams, setSearchParams] = useSearchParams();
    const textContainerRef = useRef<HTMLDivElement>(null);

    // Core data
    const [novel, setNovel] = useState<Novel | null>(null);
    const [chapters, setChapters] = useState<RawChapter[]>([]);
    const [labelGroups, setLabelGroups] = useState<LabelGroup[]>([]);

    // Selection state
    const [selectedChapterId, setSelectedChapterId] = useState<number | null>(null);
    const [chapterRevisions, setChapterRevisions] = useState<RawChapterRevisionMeta[]>([]);
    const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(null);
    const [revisionText, setRevisionText] = useState<string | null>(null);
    const [selectedLabelGroupId, setSelectedLabelGroupId] = useState<number | null>(null);

    // Label data
    const [labelData, setLabelData] = useState<LabelData | null>(null);
    const [labels, setLabels] = useState<Label[]>([]);

    // Popover state
    const [activePopover, setActivePopover] = useState<ActivePopover>(null);
    const [pendingOpError, setPendingOpError] = useState<string | null>(null);

    // Right panel state
    const [activeRightPanel, setActiveRightPanel] = useState<"labels" | "ner" | "filters">("labels");
    const [scoreThreshold, setScoreThreshold] = useState(0);
    const [entityGroupFilter, setEntityGroupFilter] = useState<Set<string>>(new Set());
    const [sortBy, setSortBy] = useState<"position" | "score" | "entityGroup" | "word">("position");
    const [searchWord, setSearchWord] = useState("");
    const [highlightedLabelId, setHighlightedLabelId] = useState<string | null>(null);

    // NER state
    const [autoLabelMeta, setAutoLabelMeta] = useState<AutoLabelMeta | null>(null);
    const [autoLabelPreview, setAutoLabelPreview] = useState<AutoLabel | null>(null);
    const [showAutoLabelPreview, setShowAutoLabelPreview] = useState(false);
    const [nerModelName, setNerModelName] = useState("");
    const [nerModelParams, setNerModelParams] = useState("{}");
    const [isRunningNer, setIsRunningNer] = useState(false);
    const [loadStatus, setLoadStatus] = useState<CreateLabelDataByAutoLabelStatus | null>(null);

    // Loading/error
    const [loading, setLoading] = useState(true);
    const [textLoading, setTextLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Derived: known entity groups from current labels
    const knownEntityGroups = useMemo(() => {
        const groups = new Set<string>();
        for (const l of labels) {
            if (l.labelEntityGroup) groups.add(l.labelEntityGroup);
        }
        return [...groups].sort();
    }, [labels]);

    // Derived: selected revision's isFinal flag
    const selectedRevisionMeta = useMemo(
        () => chapterRevisions.find((r) => r.rawChapterRevisionId === selectedRevisionId) ?? null,
        [chapterRevisions, selectedRevisionId]
    );

    // Sync query params → state on mount
    const initFromParams = useCallback(() => {
        const chapter = searchParams.get("chapter");
        const revision = searchParams.get("revision");
        const group = searchParams.get("group");
        if (chapter) setSelectedChapterId(Number(chapter));
        if (revision) setSelectedRevisionId(Number(revision));
        if (group) setSelectedLabelGroupId(Number(group));
    }, [searchParams]);

    // Fetch novel, chapters, label groups on mount
    useEffect(() => {
        if (!novel_id) return;
        const novelId = Number(novel_id);
        setLoading(true);
        setError(null);

        Promise.all([
            getNovelById(novelId),
            getChaptersByNovel(novelId),
            getLabelGroupsByNovel(novelId),
        ])
            .then(([fetchedNovel, fetchedChapters, fetchedGroups]) => {
                setNovel(fetchedNovel);
                setChapters(fetchedChapters);
                setLabelGroups(fetchedGroups);
                initFromParams();
            })
            .catch(() => setError("Failed to load workspace data"))
            .finally(() => setLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [novel_id]);

    // Fetch revisions when chapter changes
    useEffect(() => {
        if (!selectedChapterId) {
            setChapterRevisions([]);
            return;
        }
        getChapterRevisionsByChapter(selectedChapterId)
            .then(setChapterRevisions)
            .catch(() => setChapterRevisions([]));
    }, [selectedChapterId]);

    // Fetch revision text when revision changes
    useEffect(() => {
        if (!selectedRevisionId) {
            setRevisionText(null);
            return;
        }
        setTextLoading(true);
        getChapterRevisionById(selectedRevisionId)
            .then((rev) => setRevisionText(rev.rawChapterRevisionText))
            .catch(() => setRevisionText(null))
            .finally(() => setTextLoading(false));
    }, [selectedRevisionId]);

    // Fetch labels when label group + revision are both selected
    useEffect(() => {
        if (!selectedLabelGroupId || !selectedRevisionId) {
            setLabelData(null);
            setLabels([]);
            return;
        }
        getLabelDatas(selectedLabelGroupId)
            .then((allLabelDatas) => {
                const match = allLabelDatas.find((ld) => ld.rawChapterRevisionId === selectedRevisionId);
                if (!match) {
                    setLabelData(null);
                    setLabels([]);
                    return;
                }
                setLabelData(match);
                return getLabelsByLabelData(match.labelDataId).then(setLabels);
            })
            .catch(() => {
                setLabelData(null);
                setLabels([]);
            });
    }, [selectedLabelGroupId, selectedRevisionId]);

    // Fetch auto-label meta when revision changes
    useEffect(() => {
        if (!selectedRevisionId || !novel) {
            setAutoLabelMeta(null);
            setAutoLabelPreview(null);
            setShowAutoLabelPreview(false);
            setLoadStatus(null);
            return;
        }
        getAutoLabels(novel.novelId, null, [selectedRevisionId])
            .then((result) => {
                const meta = result[selectedRevisionId] ?? null;
                setAutoLabelMeta(meta);
            })
            .catch(() => setAutoLabelMeta(null));
    }, [selectedRevisionId, novel]);

    // Poll auto-label status when pending/processing
    useEffect(() => {
        if (!autoLabelMeta || !novel) return;
        const status = autoLabelMeta.autoLabelStatus;
        if (status !== "pending" && status !== "processing") return;

        const interval = setInterval(() => {
            if (!selectedRevisionId) return;
            getAutoLabels(novel.novelId, null, [selectedRevisionId])
                .then((result) => {
                    const meta = result[selectedRevisionId] ?? null;
                    setAutoLabelMeta(meta);
                    if (meta && meta.autoLabelStatus !== "pending" && meta.autoLabelStatus !== "processing") {
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
        if (selectedChapterId) params.set("chapter", String(selectedChapterId));
        if (selectedRevisionId) params.set("revision", String(selectedRevisionId));
        if (selectedLabelGroupId) params.set("group", String(selectedLabelGroupId));
        setSearchParams(params, { replace: true });
    }, [selectedChapterId, selectedRevisionId, selectedLabelGroupId, setSearchParams]);

    // Ensure labelData exists, creating it if needed
    const ensureLabelData = useCallback(async (): Promise<LabelData | null> => {
        if (labelData) return labelData;
        if (!selectedLabelGroupId || !selectedRevisionId) return null;
        const created = await createLabelDataForGroup(selectedLabelGroupId, { rawChapterRevisionId: selectedRevisionId });
        setLabelData(created);
        return created;
    }, [labelData, selectedLabelGroupId, selectedRevisionId]);

    // Optimistic label operation handler
    const handleLabelOp = useCallback(async (op: LabelOp) => {
        const ld = await ensureLabelData();
        if (!ld) return;
        const snapshot = labels;
        setLabels((prev) => applyOpToLabels(prev, op));
        setActivePopover(null);
        setPendingOpError(null);
        try {
            await updateLabelDataStream(ld.labelDataId, { ops: [op] });
        } catch {
            setLabels(snapshot);
            setPendingOpError("Failed to save label change. Reverted.");
        }
    }, [ensureLabelData, labels]);

    const handleChapterChange = (chapterId: number | null) => {
        setSelectedChapterId(chapterId);
        setSelectedRevisionId(null);
        setRevisionText(null);
        setChapterRevisions([]);
    };

    const handleRevisionChange = (revisionId: number | null) => {
        setSelectedRevisionId(revisionId);
        if (!revisionId) setRevisionText(null);
    };

    const handleLabelGroupChange = (labelGroupId: number | null) => {
        setSelectedLabelGroupId(labelGroupId);
    };

    const handleLabelGroupCreated = (labelGroup: LabelGroup) => {
        setLabelGroups((prev) => [...prev, labelGroup]);
        setSelectedLabelGroupId(labelGroup.labelGroupId);
    };

    const handleLabelClick = (label: Label, rect: DOMRect) => {
        setActivePopover({ type: "edit", label, rect });
    };

    const handleTextSelect = (selection: { startPos: number; endPos: number; text: string; rect: DOMRect }) => {
        if (!selectedLabelGroupId) return;
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
                rawChapterRevisionIds: [selectedRevisionId],
            });
            if (results.length > 0) {
                setAutoLabelMeta(results[0]);
            }
        } catch {
            setPendingOpError("Failed to start NER.");
        } finally {
            setIsRunningNer(false);
        }
    };

    const handleTogglePreview = async (show: boolean) => {
        setShowAutoLabelPreview(show);
        if (show && autoLabelMeta && !autoLabelPreview) {
            try {
                const full = await getAutoLabelById(autoLabelMeta.autoLabelId);
                setAutoLabelPreview(full);
            } catch {
                setShowAutoLabelPreview(false);
            }
        }
    };

    const handleLoadIntoGroup = async () => {
        if (!selectedLabelGroupId || !autoLabelMeta) return;
        try {
            let parsedParams = {};
            try { parsedParams = JSON.parse(nerModelParams); } catch { /* use empty */ }
            const status = await createLabelDataByAutoLabel(selectedLabelGroupId, {
                modelName: autoLabelMeta.autoLabelModelName,
                modelParams: parsedParams,
                rawChapterRevisionIds: [autoLabelMeta.rawChapterRevisionId],
            });
            setLoadStatus(status);
            // Reload labels after loading
            if (selectedRevisionId && selectedLabelGroupId) {
                const allLabelDatas = await getLabelDatas(selectedLabelGroupId);
                const match = allLabelDatas.find((ld) => ld.rawChapterRevisionId === selectedRevisionId);
                if (match) {
                    setLabelData(match);
                    const newLabels = await getLabelsByLabelData(match.labelDataId);
                    setLabels(newLabels);
                }
            }
        } catch {
            setPendingOpError("Failed to load NER results into group.");
        }
    };

    if (loading) return <div style={{ padding: "20px" }}>Loading workspace...</div>;
    if (error) return <div style={{ padding: "20px", color: "red" }}>{error}</div>;
    if (!novel) return <div style={{ padding: "20px" }}>Novel not found.</div>;

    const showAnnotated = revisionText !== null && (labels.length > 0 || selectedLabelGroupId !== null);
    const previewLabels = showAutoLabelPreview && autoLabelPreview?.autoLabelData ? autoLabelPreview.autoLabelData : null;

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
                labelGroups={labelGroups}
                selectedLabelGroupId={selectedLabelGroupId}
                onLabelGroupChange={handleLabelGroupChange}
                onLabelGroupCreated={handleLabelGroupCreated}
            />
            {pendingOpError && (
                <div style={{ padding: "6px 16px", backgroundColor: "#fee", color: "red", fontSize: "0.85rem" }}>
                    {pendingOpError}
                </div>
            )}
            <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
                <div ref={textContainerRef} style={{ flex: 1, overflow: "auto" }}>
                    {showAnnotated ? (
                        <AnnotatedText
                            text={revisionText}
                            labels={labels}
                            previewLabels={previewLabels}
                            scoreThreshold={scoreThreshold}
                            highlightedLabelId={highlightedLabelId}
                            onLabelClick={handleLabelClick}
                            onTextSelect={handleTextSelect}
                        />
                    ) : (
                        <ChapterTextViewer text={revisionText} loading={textLoading} />
                    )}
                </div>
                <div style={{ width: "320px", flexShrink: 0 }}>
                    <RightPanel activeTab={activeRightPanel} onTabChange={setActiveRightPanel}>
                        {activeRightPanel === "labels" && (
                            <LabelsPanel
                                labels={labels}
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
                                isFinal={selectedRevisionMeta?.rawChapterRevisionIsFinal ?? false}
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
                                hasSelectedGroup={selectedLabelGroupId !== null}
                            />
                        )}
                        {activeRightPanel === "filters" && (
                            <div style={{ padding: "12px", color: "#888" }}>Filters panel (deferred)</div>
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
