import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { get_novel_by_id, get_chapters_by_novel, get_chapter_revisions_by_novel } from "../api/novels";
import { type Novel, type RawChapter, type RawChapterRevisionMeta } from '../types/novel';
import { AppRoutes, routeTo } from "../routes";

export const NovelDetailsPage = () => {
    const { novel_id } = useParams<{ novel_id: string }>();
    const [novel, setNovel] = useState<Novel | null>(null);
    const [chapters, setChapters] = useState<RawChapter[]>([]);
    
    // Using a Map to store revisions: ChapterID -> List of Revisions
    const [chapterRevisions, setChapterRevisions] = useState<Map<number, RawChapterRevisionMeta[]>>(new Map());

    useEffect(() => {
        if (typeof novel_id === "undefined") return;
        const novelId = Number(novel_id);

        // 1. Fetch the Novel
        get_novel_by_id(novelId).then((fetchedNovel) => {
            setNovel(fetchedNovel);

            // 2. ONLY after we have the novel (or just using the ID), fetch the rest
            // We can run these two in parallel
            Promise.all([
                get_chapters_by_novel(novelId),
                get_chapter_revisions_by_novel(novelId)
            ]).then(([fetchedChapters, fetchedRevisions]) => {
                
                setChapters(fetchedChapters);

                // 3. Process Revisions into the Map
                const map = new Map<number, RawChapterRevisionMeta[]>();
                fetchedRevisions.forEach((rev) => {
                    const existing = map.get(rev.raw_chapter_id) || [];
                    existing.push(rev);
                    map.set(rev.raw_chapter_id, existing);
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
                <h1>{novel.novel_title}</h1>
                <p style={{ color: '#555' }}>Author: {novel.novel_author || 'Unknown'}</p>
                <div style={{ display: 'flex', gap: '10px' }}>
                    <span style={{ background: '#eee', padding: '4px 8px', borderRadius: '4px' }}>
                        {novel.novel_type}
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
                    const revs = chapterRevisions.get(chapter.raw_chapter_id) || [];
                    const primaryRev = revs.find(r => r.raw_chapter_revision_is_primary);

                    return (
                        <div key={chapter.raw_chapter_id} style={{ 
                            border: '1px solid #eee', 
                            padding: '15px', 
                            borderRadius: '8px',
                            backgroundColor: '#fafafa'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <h3 style={{ margin: 0, fontSize: '1.1rem' }}>
                                    Chapter {chapter.raw_chapter_num}
                                    {/* Show title if available, otherwise fallback */}
                                    {primaryRev && `: ${primaryRev.raw_chapter_revision_title}`}
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
                                            <li key={rev.raw_chapter_revision_id} style={{ marginBottom: '4px' }}>
                                                <Link to={routeTo.view.chapter(rev.raw_chapter_id, { revisionId: rev.raw_chapter_revision_id })} style={{ color: rev.raw_chapter_revision_is_primary ? 'green' : 'blue' }}>
                                                    {rev.raw_chapter_revision_title || 'Untitled Revision'}
                                                </Link>
                                                {rev.raw_chapter_revision_is_primary && 
                                                    <span style={{ fontSize: '0.7rem', marginLeft: '8px', background: '#d4edda', padding: '2px 4px', borderRadius: '4px' }}>PRIMARY</span>
                                                }
                                                {(rev.raw_chapter_revision_is_public && !rev.raw_chapter_revision_is_primary) && 
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