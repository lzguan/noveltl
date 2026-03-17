import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { getNovelById, getChaptersByNovel, getChapterRevisionsByChapter, getChapterRevisionById } from "../api/novels";
import { getLabelGroupsByNovel, getLabelDatas, getLabelsByLabelData } from "../api/labels";
import { type Novel, type RawChapter, type RawChapterRevisionMeta } from "../types/novel";
import { type LabelGroup, type LabelData, type Label } from "../types/label";
import { SelectorsBar } from "../components/workspace/SelectorsBar";
import { ChapterTextViewer } from "../components/workspace/ChapterTextViewer";
import { AnnotatedText } from "../components/workspace/AnnotatedText";

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
    const [, setLabelData] = useState<LabelData | null>(null);
    const [labels, setLabels] = useState<Label[]>([]);

    // Loading/error
    const [loading, setLoading] = useState(true);
    const [textLoading, setTextLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

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

    if (loading) return <div style={{ padding: "20px" }}>Loading workspace...</div>;
    if (error) return <div style={{ padding: "20px", color: "red" }}>{error}</div>;
    if (!novel) return <div style={{ padding: "20px" }}>Novel not found.</div>;

    const showAnnotated = revisionText !== null && labels.length > 0;

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
            {showAnnotated ? (
                <AnnotatedText text={revisionText} labels={labels} />
            ) : (
                <ChapterTextViewer text={revisionText} loading={textLoading} />
            )}
        </div>
    );
};
