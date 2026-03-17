import { useState } from "react";
import { type Novel, type RawChapter, type RawChapterRevisionMeta } from "../../types/novel";
import { type LabelGroup, type CreateLabelGroup } from "../../types/label";
import { createLabelGroup } from "../../api/labels";

type SelectorsBarProps = {
    novel: Novel;
    chapters: RawChapter[];
    selectedChapterId: number | null;
    onChapterChange: (chapterId: number | null) => void;
    chapterRevisions: RawChapterRevisionMeta[];
    selectedRevisionId: number | null;
    onRevisionChange: (revisionId: number | null) => void;
    labelGroups: LabelGroup[];
    selectedLabelGroupId: number | null;
    onLabelGroupChange: (labelGroupId: number | null) => void;
    onLabelGroupCreated: (labelGroup: LabelGroup) => void;
};

export const SelectorsBar: React.FC<SelectorsBarProps> = ({
    novel,
    chapters,
    selectedChapterId,
    onChapterChange,
    chapterRevisions,
    selectedRevisionId,
    onRevisionChange,
    labelGroups,
    selectedLabelGroupId,
    onLabelGroupChange,
    onLabelGroupCreated,
}) => {
    const [newGroupName, setNewGroupName] = useState("");
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);

    const sortedChapters = [...chapters].sort((a, b) => a.rawChapterNum - b.rawChapterNum);

    const handleCreateGroup = async () => {
        const name = newGroupName.trim();
        if (!name) return;
        setIsCreating(true);
        setCreateError(null);
        try {
            const request: CreateLabelGroup = { labelGroupName: name, novelId: novel.novelId };
            const created = await createLabelGroup(request);
            onLabelGroupCreated(created);
            setNewGroupName("");
        } catch {
            setCreateError("Failed to create label group");
        } finally {
            setIsCreating(false);
        }
    };

    return (
        <div style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            padding: "12px 16px",
            borderBottom: "1px solid #ddd",
            backgroundColor: "#fafafa",
            flexWrap: "wrap",
        }}>
            <strong style={{ fontSize: "1.1rem", marginRight: "8px" }}>{novel.novelTitle}</strong>

            <label style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                Chapter:
                <select
                    value={selectedChapterId ?? ""}
                    onChange={(e) => onChapterChange(e.target.value ? Number(e.target.value) : null)}
                >
                    <option value="">-- Select --</option>
                    {sortedChapters.map((ch) => (
                        <option key={ch.rawChapterId} value={ch.rawChapterId}>
                            Ch. {ch.rawChapterNum}
                        </option>
                    ))}
                </select>
            </label>

            <label style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                Revision:
                <select
                    value={selectedRevisionId ?? ""}
                    onChange={(e) => onRevisionChange(e.target.value ? Number(e.target.value) : null)}
                    disabled={!selectedChapterId}
                >
                    <option value="">-- Select --</option>
                    {chapterRevisions.map((rev) => (
                        <option key={rev.rawChapterRevisionId} value={rev.rawChapterRevisionId}>
                            {rev.rawChapterRevisionTitle || `Revision ${rev.rawChapterRevisionId}`}
                        </option>
                    ))}
                </select>
            </label>

            <label style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                Label Group:
                <select
                    value={selectedLabelGroupId ?? ""}
                    onChange={(e) => onLabelGroupChange(e.target.value ? Number(e.target.value) : null)}
                >
                    <option value="">-- Select --</option>
                    {labelGroups.map((lg) => (
                        <option key={lg.labelGroupId} value={lg.labelGroupId}>
                            {lg.labelGroupName}
                        </option>
                    ))}
                </select>
            </label>

            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <input
                    type="text"
                    placeholder="New group name"
                    value={newGroupName}
                    onChange={(e) => setNewGroupName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") void handleCreateGroup(); }}
                    style={{ width: "130px", padding: "2px 6px" }}
                />
                <button onClick={() => void handleCreateGroup()} disabled={isCreating || !newGroupName.trim()}>
                    {isCreating ? "..." : "+"}
                </button>
                {createError && <span style={{ color: "red", fontSize: "0.8rem" }}>{createError}</span>}
            </div>
        </div>
    );
};
