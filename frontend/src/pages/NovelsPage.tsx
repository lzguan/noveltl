import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { get_novels, get_novels_mine } from '../api/novels';
import { type Novel } from '../types/novel';
import { NovelCard } from '../components/novels/NovelCard';

export const NovelsPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();

    const [novels, setNovels] = useState<Novel[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchData = async () => {
            const isMine = searchParams.get('mine') === 'true';
            const search = searchParams.get('search') || undefined;
            setLoading(true);
            setError('');
            try {
                const data = isMine
                    ? await get_novels_mine(false, search)
                    : await get_novels(typeof search !== 'undefined' ? search : '');
                setNovels(data);
            } catch (err) {
                console.error(err);
                setError(isMine 
                    ? 'Failed to fetch your novels. Are you logged in?' 
                    : 'Failed to fetch novels. Is the backend running?'
                );
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [searchParams]);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        const form = e.target as HTMLFormElement;
        const input = form.elements.namedItem('search') as HTMLInputElement;
        const params = new URLSearchParams(searchParams);
        if (input.value) {
            params.set('search', input.value);
        } else {
            params.delete('search');
        }
        navigate(`?${params.toString()}`);
    };

    return (
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}>
            
            <div style={{ marginBottom: '30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h1>{searchParams.get('mine') === 'true' ? 'My Novels' : 'Library'}</h1>
                
                <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
                    <input 
                        name="search"
                        type="text" 
                        placeholder="Search titles..." 
                        defaultValue={searchParams.get('search') || undefined}
                        style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
                    />
                    <button type="submit" style={{ padding: '8px 16px', background: '#333', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                        Search
                    </button>
                </form>
            </div>

            {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}
            {loading && <p>Loading novels...</p>}
            {!loading && novels.length === 0 && (
                <p style={{ textAlign: 'center', color: '#777', marginTop: '40px' }}>
                    {searchParams.get('mine') === 'true' ? "You don't have any novels yet." : 'No novels found. Try a different search or add one!'}
                </p>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
                {novels.map((novel) => (
                    <NovelCard key={novel.novel_id} novel={novel} />
                ))}
            </div>
        </div>
    );
};