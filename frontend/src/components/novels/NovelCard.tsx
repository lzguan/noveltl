import { type Novel, Visibility } from '../../types/novel';
import { Link } from 'react-router-dom';

interface NovelCardProps {
    novel: Novel;
}

// Helper to get text/color for the status
const getVisibilityLabel = (vis: number) => {
    switch (vis) {
        case Visibility.private: return { text: 'Private', color: '#e74c3c' };    // Red
        case Visibility.restricted: return { text: 'Restricted', color: '#f39c12' }; // Orange
        case Visibility.unlisted: return { text: 'Unlisted', color: '#95a5a6' };  // Grey
        case Visibility.public: return { text: 'Public', color: '#2ecc71' };      // Green
        default: return { text: 'Unknown', color: '#000' };
    }
};

export const NovelCard = ({ novel }: NovelCardProps) => {
    const badge = getVisibilityLabel(novel.novel_visibility);

    return (
        <div style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '16px',
            backgroundColor: '#fff',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
        }}>
            {/* Header: Title + Badge */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem' }}>{novel.novel_title}</h3>
                <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    backgroundColor: badge.color,
                    color: 'white'
                }}>
                    {badge.text}
                </span>
            </div>

            {/* Meta Info */}
            <p style={{ margin: 0, color: '#666', fontSize: '0.9rem' }}>
                {novel.novel_author || "Unknown Author"}
            </p>
            
            <p style={{ margin: 0, fontSize: '0.85rem', color: '#888' }}>
                Type: {novel.novel_type}
            </p>

            {/* Action Button (Placeholder) */}
            <Link to={`/view/novels/${novel.novel_id}`}>
                <button style={{
                    marginTop: '10px',
                    padding: '8px',
                    border: '1px solid #ccc',
                    background: 'transparent',
                    cursor: 'pointer',
                    borderRadius: '4px'
                }}>
                    View details
                </button>
            </Link>
        </div>
    );
};