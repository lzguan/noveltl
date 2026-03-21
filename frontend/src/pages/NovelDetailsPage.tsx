import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getNovelById, getChaptersByNovel, getChapterRevisionsByNovel } from "../api/novels";
import { type Novel, type Chapter, type RevisionMeta } from '../types/novel';
import { AppRoutes, routeTo } from "../routes";

export const NovelDetailsPage = () => {
    const { novel_id } = useParams<{ novel_id: string }>();
    const [novel, setNovel] = useState<Novel | null>(null);
    const [chapters, setChapters] = useState<Chapter[]>([]);

    // Using a Map to store revisions: ChapterID -> List of Revisions
    const [chapterRevisions, setChapterRevisions] = useState<Map<number, RevisionMeta[]>>(new Map());

    useEffect(() => {
        if (typeof novel_id === "undefined") return;
        const novelId = Number(novel_id);

        // 1. Fetch the Novel
        getNovelById(novelId).then((fetchedNovel) => {
            setNovel(fetchedNovel);

            // 2. ONLY after we have the novel (or just using the ID), fetch the rest
            // We can run these two in parallel
            Promise.all([
                getChaptersByNovel(novelId),
                getChapterRevisionsByNovel(novelId)
            ]).then(([fetchedChapters, fetchedRevisions]) => {
                
                setChapters(fetchedChapters);

                // 3. Process Revisions into the Map
                const map = new Map<number, RevisionMeta[]>();
                fetchedRevisions.forEach((rev) => {
                    const existing = map.get(rev.chapterId) || [];
                    existing.push(rev);
                    map.set(rev.chapterId, existing);
                });
                setChapterRevisions(map);
            });
        });
    }, [novel_id]);

    if (!novel) return <div>Loading...</div>;

    return (
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
            
            {/* Header Section */}
            <div style={{ borderBottom: '1px solid #ddd', paddingBottom: '20px', marginBottom: '20px' }}>
                <Link to={AppRoutes.VIEW.NOVELS} style={{ textDecoration: 'none', color: '#666' }}>&larr; Back to Library</Link>
                <h1>{novel.novelTitle}</h1>
                <p style={{ color: '#555' }}>Author: {novel.novelAuthor || 'Unknown'}</p>
                <div style={{ display: 'flex', gap: '10px' }}>
                    <span style={{ background: '#eee', padding: '4px 8px', borderRadius: '4px' }}>
                        {novel.novelType}
                    </span>
                    {/* Add more metadata badges here if needed */}
                </div>
            </div>

            {/* Chapters List */}
            <h2>Chapters ({chapters.length})</h2>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                {chapters.length === 0 && <p>No chapters yet.</p>}

                {chapters.map((chapter) => {
                    // Look up revisions for this chapter
                    const revs = chapterRevisions.get(chapter.chapterId) || [];
                    const primaryRev = revs.find(r => r.revisionIsPrimary);

                    return (
                        <div key={chapter.chapterId} style={{ 
                            border: '1px solid #eee', 
                            padding: '15px', 
                            borderRadius: '8px',
                            backgroundColor: '#fafafa'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <h3 style={{ margin: 0, fontSize: '1.1rem' }}>
                                    Chapter {chapter.chapterNum}
                                    {/* Show title if available, otherwise fallback */}
                                    {primaryRev && `: ${primaryRev.revisionTitle}`}
                                </h3>
                            </div>

                            {/* Revisions List */}
                            <div style={{ marginTop: '10px', paddingLeft: '10px', borderLeft: '2px solid #ddd' }}>
                                <p style={{ fontSize: '0.8rem', color: '#888', margin: '0 0 5px 0' }}>Revisions:</p>
                                
                                {revs.length === 0 ? (
                                    <span style={{ color: '#999', fontSize: '0.9rem' }}>No revisions found.</span>
                                ) : (
                                    <ul style={{ margin: 0, paddingLeft: '20px' }}>
                                        {revs.map(rev => (
                                            <li key={rev.revisionId} style={{ marginBottom: '4px' }}>
                                                <Link to={routeTo.view.chapter(rev.chapterId, { revisionId: rev.revisionId })} style={{ color: rev.revisionIsPrimary ? 'green' : 'blue' }}>
                                                    {rev.revisionTitle || 'Untitled Revision'}
                                                </Link>
                                                {rev.revisionIsPrimary && 
                                                    <span style={{ fontSize: '0.7rem', marginLeft: '8px', background: '#d4edda', padding: '2px 4px', borderRadius: '4px' }}>PRIMARY</span>
                                                }
                                                {(rev.revisionIsPublic && !rev.revisionIsPrimary) && 
                                                    <span style={{ fontSize: '0.7rem', marginLeft: '4px', background: '#cce5ff', padding: '2px 4px', borderRadius: '4px' }}>PUBLIC</span>
                                                }
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};