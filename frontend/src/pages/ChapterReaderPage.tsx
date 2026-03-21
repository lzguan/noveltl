import { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { getChapterById, getChapterRevisionsByChapter } from "../api/novels";
import { type Chapter, type RevisionMeta } from "../types/novel";
import { RevisionSidebar } from "../components/novels/RevisionSidebar";
import { RevisionContentDisplay } from "../components/novels/RevisionContentDisplay";
import { routeTo } from "../routes";

export const ChapterReaderPage = () => {
    const { chapter_id } = useParams<{ chapter_id: string }>();
    const chapterId = Number(chapter_id);

    const [searchParams] = useSearchParams();
    const urlRevisionId = searchParams.get("revision_id") ? Number(searchParams.get("revision_id")) : null;

    const [chapter, setChapter] = useState<Chapter | null>(null);
    const [revisionList, setRevisionList] = useState<RevisionMeta[]>([]);
    
    // Derived State: We are "loading" if we don't have a chapter, 
    // OR if the chapter we have doesn't match the URL ID (stale data).
    const isLoading = !chapter || chapter.chapterId !== chapterId;

    useEffect(() => {
        if (!chapterId) return;

        // NO setLoading(true) here! The 'isLoading' derived check handles it.

        Promise.all([
            getChapterById(chapterId),
            getChapterRevisionsByChapter(chapterId)
        ]).then(([chapData, revList]) => {
            setChapter(chapData);
            setRevisionList(revList);
        }).catch(console.error);
        
    }, [chapterId]);

    // Fallback active ID logic
    const activeRevisionId = urlRevisionId ?? (revisionList.length > 0 ? revisionList[0].revisionId : null);

    if (isLoading) return <div style={{ padding: '20px' }}>Loading chapter...</div>;
    // Type guard: simple check to satisfy TS, though isLoading covers it
    if (!chapter) return <div style={{ padding: '20px' }}>Chapter not found.</div>;

    return (
        <div style={{ display: 'flex', height: '100vh', flexDirection: 'column' }}>
            <div style={{ padding: '10px 20px', borderBottom: '1px solid #ddd', display: 'flex', alignItems: 'center', gap: '20px', backgroundColor: '#fff' }}>
                <Link to={routeTo.view.novel(chapter.novelId)} style={{ textDecoration: 'none', color: '#666' }}>
                    &larr; Back to Novel
                </Link>
                <h3 style={{ margin: 0 }}>Chapter {chapter.chapterNum}</h3>
                <div style={{ flex: 1 }}></div>
            </div>

            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                <div style={{ width: '260px', borderRight: '1px solid #ddd', overflowY: 'auto' }}>
                    {/* KEY PROP MAGIC: passing key={chapterId} forces this component to 
                        unmount/remount when the chapter changes. This resets its internal 
                        'loading' state to true automatically. */}
                    <RevisionSidebar 
                        key={chapterId}
                        chapterId={chapterId} 
                        activeRevisionId={activeRevisionId} 
                    />
                </div>

                <div style={{ flex: 1, overflowY: 'auto', backgroundColor: '#f5f5f5', padding: '20px' }}>
                     {/* KEY PROP MAGIC: same here. When ID changes, it remounts fresh. */}
                    <RevisionContentDisplay 
                        key={activeRevisionId ?? 'empty'}
                        revisionId={activeRevisionId} 
                    />
                </div>
            </div>
        </div>
    );
};