import { type Novel, type Chapter, type Revision } from "../../types/novel";

type WorkspaceMode = "edit" | "label";

type SelectorsBarProps = {
    novel: Novel;
    chapters: Chapter[];
    selectedChapterId: string | null;
    onChapterChange: (chapterId: string | null) => void;
    chapterRevisions: Revision[];
    selectedRevisionId: string | null;
    onRevisionChange: (revisionId: string | null) => void;
    mode: WorkspaceMode;
    onModeChange: (mode: WorkspaceMode) => void;
};

export const SelectorsBar: React.FC<SelectorsBarProps> = ({
    novel,
    chapters,
    selectedChapterId,
    onChapterChange,
    chapterRevisions,
    selectedRevisionId,
    onRevisionChange,
    mode,
    onModeChange,
}) => {
    const sortedChapters = [...chapters].sort((a, b) => a.chapterNum - b.chapterNum);

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
                    onChange={(e) => onChapterChange(e.target.value || null)}
                >
                    <option value="">-- Select --</option>
                    {sortedChapters.map((ch) => (
                        <option key={ch.chapterId} value={ch.chapterId}>
                            Ch. {ch.chapterNum}
                        </option>
                    ))}
                </select>
            </label>

            <label style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                Revision:
                <select
                    value={selectedRevisionId ?? ""}
                    onChange={(e) => onRevisionChange(e.target.value || null)}
                    disabled={!selectedChapterId}
                >
                    <option value="">-- Select --</option>
                    {chapterRevisions.map((rev) => (
                        <option key={rev.revisionId} value={rev.revisionId}>
                            {rev.revisionTitle || `Revision ${rev.revisionId}`}
                        </option>
                    ))}
                </select>
            </label>

            <div style={{ display: "flex", marginLeft: "auto" }}>
                {(["edit", "label"] as const).map((m) => (
                    <button
                        key={m}
                        onClick={() => onModeChange(m)}
                        style={{
                            padding: "4px 14px",
                            border: "none",
                            borderBottom: mode === m ? "2px solid #4a90d9" : "2px solid transparent",
                            background: "none",
                            fontWeight: mode === m ? 600 : 400,
                            color: mode === m ? "#4a90d9" : "#666",
                            cursor: "pointer",
                            fontSize: "0.9rem",
                        }}
                    >
                        {m === "edit" ? "Edit" : "Label"}
                    </button>
                ))}
            </div>
        </div>
    );
};
