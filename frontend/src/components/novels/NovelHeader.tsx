import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getNovelById } from "../../api/novels";
import { type Novel } from "../../types/novel";
import { routeTo } from "../../routes";

interface NovelHeaderProps {
    novelId: string;
}

export const NovelHeader = ({ novelId }: NovelHeaderProps) => {
    const [novel, setNovel] = useState<Novel | null>(null);

    useEffect(() => {
        getNovelById(novelId).then(setNovel).catch(console.error);
    }, [novelId]);

    if (!novel) return <div>Loading novel info...</div>;

    return (
        <div style={{ marginBottom: '10px' }}>
            <Link to={routeTo.view.novel(novel.novelId)} style={{ textDecoration: 'none', color: '#666', fontSize: '0.9rem' }}>
                &larr; Back to {novel.novelTitle}
            </Link>
        </div>
    );
};