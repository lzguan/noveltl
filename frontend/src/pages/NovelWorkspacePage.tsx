import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { getNovelById, getChaptersByNovel, getChapterRevisionsByChapter, getChapterRevisionById } from "../api/novels";
import { getLabelGroupsByNovel, getLabelDatas, getLabelsByLabelData, updateLabelDataStream, createLabelDataForGroup } from "../api/labels";
import { type Novel, type RawChapter, type RawChapterRevisionMeta } from "../types/novel";
import { type LabelGroup, type LabelData, type Label, type LabelOp, type AddLabelOp } from "../types/label";
import { applyOpToLabels } from "../components/workspace/labelOps";
import { SelectorsBar } from "../components/workspace/SelectorsBar";
import { ChapterTextViewer } from "../components/workspace/ChapterTextViewer";
import { AnnotatedText } from "../components/workspace/AnnotatedText";
import { LabelPopover } from "../components/workspace/LabelPopover";
import { NewLabelPopover } from "../components/workspace/NewLabelPopover";

type ActivePopover =
    | { type: "edit"; label: Label; rect: DOMRect }
    | { type: "new"; startPos: number; endPos: number; text: string; rect: DOMRect }
    | null;

export const NovelWorkspacePage = () => {
    const { novel_id } = useParams<{ novel_id: string }>();
    const [searchParams, setSearchParams] = useSearchParams();

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

    // Sync state → query params
    useEffect(() => {
        const params = new URLSearchParams();
        if (selectedChapterId) params.set("chapter", String(selectedChapterId));
        if (selectedRevisionId) params.set("revision", String(selectedRevisionId));
        if (selectedLabelGroupId) params.set("group", String(selectedLabelGroupId));
        setSearchParams(params, { replace: true });
    }, [selectedChapterId, selectedRevisionId, selectedLabelGroupId, setSearchParams]);

    // Ensure labelData exists, creating it if needed (for first label on empty revision/group)
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

    if (loading) return <div style={{ padding: "20px" }}>Loading workspace...</div>;
    if (error) return <div style={{ padding: "20px", color: "red" }}>{error}</div>;
    if (!novel) return <div style={{ padding: "20px" }}>Novel not found.</div>;

    const showAnnotated = revisionText !== null && (labels.length > 0 || selectedLabelGroupId !== null);

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
            {showAnnotated ? (
                <AnnotatedText
                    text={revisionText}
                    labels={labels}
                    onLabelClick={handleLabelClick}
                    onTextSelect={handleTextSelect}
                />
            ) : (
                <ChapterTextViewer text={revisionText} loading={textLoading} />
            )}
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
