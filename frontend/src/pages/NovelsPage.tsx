import { useEffect, useState } from 'react';
import { get_novels } from '../api/novels'; // Ensure this matches your filename
import { type Novel } from '../types/novel';
import { NovelCard } from '../components/novels/NovelCard';

export const NovelsPage = () => {
    const [novels, setNovels] = useState<Novel[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [error, setError] = useState('');

    // The fetch function
    const fetchData = async (searchTerm = '') => {
        setLoading(true);
        setError('');
        try {
            const data = await get_novels(searchTerm);
            setNovels(data);
        } catch (err) {
            console.error(err);
            setError('Failed to fetch novels. Is the backend running?');
        } finally {
            setLoading(false);
        }
    };

    // Initial load
    useEffect(() => {
        fetchData();
    }, []);

    // Handle Search Submit
    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        fetchData(search);
    };

    return (
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
            
            {/* Header & Search Section */}
            <div style={{ marginBottom: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h1>Library</h1>
                
                <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
                    <input 
                        type="text" 
                        placeholder="Search titles..." 
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
                    />
                    <button type="submit" style={{ padding: '8px 16px', background: '#333', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                        Search
                    </button>
                </form>
            </div>

            {/* Error Message */}
            {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}

            {/* Loading State */}
            {loading && <p>Loading novels...</p>}

            {/* Empty State */}
            {!loading && novels.length === 0 && (
                <p style={{ textAlign: 'center', color: '#777', marginTop: '40px' }}>
                    No novels found. Try a different search or add one!
                </p>
            )}

            {/* Grid Layout */}
            <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
                gap: '20px' 
            }}>
                {novels.map((novel) => (
                    <NovelCard key={novel.novel_id} novel={novel} />
                ))}
            </div>
        </div>
    );
};