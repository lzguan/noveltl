import { useEffect, useState } from "react";
import { getChapterRevisionById, getRevisionText } from "../../api/novels";
import { type Revision, type RevisionText } from "../../types/novel";

interface RevisionContentDisplayProps {
    revisionId: string | null;
}

export const RevisionContentDisplay = ({ revisionId }: RevisionContentDisplayProps) => {
    const [loading, setLoading] = useState(!!revisionId);
    const [revision, setRevision] = useState<Revision | null>(null);
    const [revisionText, setRevisionText] = useState<RevisionText | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!revisionId) return;

        let mounted = true;

        Promise.all([
            getChapterRevisionById(revisionId),
            getRevisionText(revisionId)
        ])
            .then(([revData, textData]) => {
                if (mounted) {
                    setRevision(revData);
                    setRevisionText(textData);
                    setLoading(false);
                }
            })
            .catch((err) => {
                if (mounted) {
                    console.error(err);
                    setError("Failed to load revision content.");
                    setLoading(false);
                }
            });

        return () => { mounted = false; };
    }, [revisionId]);

    if (loading) {
        return <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>Loading content...</div>;
    }

    if (!revisionId) {
        return (
            <div style={{
                padding: '40px',
                textAlign: 'center',
                backgroundColor: '#fff0f0',
                border: '1px dashed #ffa0a0',
                borderRadius: '8px',
                color: '#d63031',
                marginTop: '20px'
            }}>
                <h3>No Content Available</h3>
                <p>There are no revisions for this chapter yet.</p>
            </div>
        );
    }

    if (error) return <div style={{ color: 'red', textAlign: 'center', marginTop: '20px' }}>{error}</div>;
    if (!revision || !revisionText) return null;

    return (
        <div style={{
            maxWidth: '800px',
            margin: '0 auto',
            lineHeight: '1.8',
            fontSize: '1.15rem',
            fontFamily: 'Georgia, serif',
            backgroundColor: '#fff',
            padding: '40px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.05)',
            borderRadius: '4px'
        }}>
            <h2 style={{ textAlign: 'center', marginBottom: '30px' }}>{revision.revisionTitle}</h2>
            <div style={{ whiteSpace: 'pre-wrap' }}>{revisionText.revisionTextContent}</div>
        </div>
    );
};
