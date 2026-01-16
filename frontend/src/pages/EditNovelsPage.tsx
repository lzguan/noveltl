import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { /*create_novel,*/ get_novels_mine } from '../api/novels';
import { type Novel } from '../types/novel';
import { routeTo } from '../routes';
import { Modal } from '../components/common/modal';
import { CreateNovelForm } from '../components/novels/CreateNovelForm';

// Helper for visibility badge
const getVisibilityBadge = (vis: number) => {
    const map: Record<number, { text: string; color: string }> = {
        0: { text: 'Private', color: '#e74c3c' },
        1: { text: 'Restricted', color: '#f39c12' },
        2: { text: 'Unlisted', color: '#95a5a6' },
        3: { text: 'Public', color: '#2ecc71' },
    };
    return map[vis] ?? { text: 'Unknown', color: '#000' };
};

export const EditNovelsPage = () => {
    const [novels, setNovels] = useState<Novel[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const navigate = useNavigate();

    // handleNewNovel = async () => {
    //     // Navigate to the new novel creation page
    //     novel = await create_novel()
    // }

    useEffect(() => {
        const fetchNovels = async () => {
            setLoading(true);
            setError('');
            try {
                // Get all novels user can edit (owner/editor)
                const data = await get_novels_mine(true);
                setNovels(data);
            } catch (err) {
                console.error(err);
                setError('Failed to fetch your novels. Are you logged in?');
            } finally {
                setLoading(false);
            }
        };
        fetchNovels();
    }, []);

    return (
        <>
            <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '20px' }}>
                {/* Header */}
                <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    marginBottom: '24px'
                }}>
                    <h1 style={{ margin: 0 }}>My Novels</h1>
                    <button
                        onClick={() => {
                            setIsModalOpen(true);
                        }}
                        style={{
                            padding: '10px 20px',
                            backgroundColor: '#2ecc71',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontWeight: 'bold'
                        }}
                    >
                        + New Novel
                    </button>
                </div>

                {/* Error */}
                {error && (
                    <div style={{ 
                        padding: '12px', 
                        backgroundColor: '#ffe6e6', 
                        color: '#c00', 
                        borderRadius: '6px',
                        marginBottom: '16px'
                    }}>
                        {error}
                    </div>
                )}

                {/* Loading */}
                {loading && <p>Loading your novels...</p>}

                {/* Empty State */}
                {!loading && novels.length === 0 && (
                    <div style={{ 
                        textAlign: 'center', 
                        padding: '60px 20px',
                        color: '#888'
                    }}>
                        <p style={{ fontSize: '1.1rem' }}>You don't have any novels yet.</p>
                        <p>Click "New Novel" to create your first project!</p>
                    </div>
                )}

                {/* Table */}
                {!loading && novels.length > 0 && (
                    <table style={{ 
                        width: '100%', 
                        borderCollapse: 'collapse',
                        backgroundColor: '#fff',
                        borderRadius: '8px',
                        overflow: 'hidden',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                    }}>
                        <thead>
                            <tr style={{ backgroundColor: '#f8f9fa', textAlign: 'left' }}>
                                <th style={{ padding: '14px 16px', fontWeight: '600' }}>Title</th>
                                <th style={{ padding: '14px 16px', fontWeight: '600' }}>Type</th>
                                <th style={{ padding: '14px 16px', fontWeight: '600' }}>Visibility</th>
                                <th style={{ padding: '14px 16px', fontWeight: '600', textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {novels.map((novel) => {
                                const badge = getVisibilityBadge(novel.novel_visibility);
                                return (
                                    <tr 
                                        key={novel.novel_id}
                                        style={{ 
                                            borderTop: '1px solid #eee',
                                            cursor: 'pointer'
                                        }}
                                        onClick={() => navigate(routeTo.edit.novel(novel.novel_id))}
                                    >
                                        <td style={{ padding: '14px 16px' }}>
                                            <span style={{ fontWeight: '500' }}>{novel.novel_title}</span>
                                            {novel.novel_author && (
                                                <span style={{ color: '#888', marginLeft: '8px', fontSize: '0.9rem' }}>
                                                    by {novel.novel_author}
                                                </span>
                                            )}
                                        </td>
                                        <td style={{ padding: '14px 16px', color: '#666', textTransform: 'capitalize' }}>
                                            {novel.novel_type}
                                        </td>
                                        <td style={{ padding: '14px 16px' }}>
                                            <span style={{
                                                fontSize: '0.8rem',
                                                padding: '4px 10px',
                                                borderRadius: '12px',
                                                backgroundColor: badge.color,
                                                color: 'white',
                                                fontWeight: '500'
                                            }}>
                                                {badge.text}
                                            </span>
                                        </td>
                                        <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                                            <Link 
                                                to={routeTo.view.novel(novel.novel_id)}
                                                onClick={(e) => e.stopPropagation()}
                                                style={{ marginRight: '12px', color: '#3498db' }}
                                                title="View"
                                            >
                                                👁️
                                            </Link>
                                            <Link 
                                                to={routeTo.edit.novel(novel.novel_id)}
                                                onClick={(e) => e.stopPropagation()}
                                                style={{ color: '#f39c12' }}
                                                title="Edit"
                                            >
                                                ✏️
                                            </Link>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Create New Novel">
                <CreateNovelForm onClose={() => setIsModalOpen(false)} />
            </Modal>
        </>
    );
};