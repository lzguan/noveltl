import React from "react";
import { type Label, type LabelGroup } from "../../types/label";
import { getEntityGroupColor } from "./labelOps";
import { LabelGroupSelector } from "./LabelGroupSelector";

type SortBy = "position" | "score" | "entityGroup" | "word";

type LabelsPanelProps = {
    labelGroups: LabelGroup[];
    selectedGroupId: string | null;
    onGroupChange: (groupId: string | null) => void;
    novelId: string;
    onGroupCreated: (labelGroup: LabelGroup) => void;
    labels: Label[];
    scoreThreshold: number;
    onScoreThresholdChange: (value: number) => void;
    entityGroupFilter: Set<string>;
    onEntityGroupFilterToggle: (group: string) => void;
    sortBy: SortBy;
    onSortByChange: (value: SortBy) => void;
    searchWord: string;
    onSearchWordChange: (value: string) => void;
    onLabelClick: (label: Label) => void;
};

const sortLabels = (labels: Label[], sortBy: SortBy): Label[] => {
    const sorted = [...labels];
    switch (sortBy) {
        case "position":
            return sorted.sort((a, b) => a.labelStart - b.labelStart);
        case "score":
            return sorted.sort((a, b) => b.labelScore - a.labelScore);
        case "entityGroup":
            return sorted.sort((a, b) => (a.labelEntityGroup ?? "").localeCompare(b.labelEntityGroup ?? ""));
        case "word":
            return sorted.sort((a, b) => a.labelWord.localeCompare(b.labelWord));
        default:
            return sorted;
    }
};

export const LabelsPanel: React.FC<LabelsPanelProps> = ({
    labelGroups,
    selectedGroupId,
    onGroupChange,
    novelId,
    onGroupCreated,
    labels,
    scoreThreshold,
    onScoreThresholdChange,
    entityGroupFilter,
    onEntityGroupFilterToggle,
    sortBy,
    onSortByChange,
    searchWord,
    onSearchWordChange,
    onLabelClick,
}) => {
    // Collect all entity groups
    const allGroups = [...new Set(labels.map((l) => l.labelEntityGroup).filter(Boolean) as string[])].sort();

    // Filter labels
    const filtered = labels.filter((l) => {
        if (entityGroupFilter.size > 0 && !entityGroupFilter.has(l.labelEntityGroup ?? "")) return false;
        if (searchWord && !l.labelWord.toLowerCase().includes(searchWord.toLowerCase())) return false;
        return true;
    });

    const belowThreshold = filtered.filter((l) => l.labelScore < scoreThreshold).length;
    const sorted = sortLabels(filtered, sortBy);

    return (
        <div style={{ fontSize: "0.85rem" }}>
            <LabelGroupSelector
                labelGroups={labelGroups}
                selectedGroupId={selectedGroupId}
                onGroupChange={onGroupChange}
                novelId={novelId}
                onGroupCreated={onGroupCreated}
            />
            <div style={{ padding: "12px" }}>
            {/* Counter */}
            <div style={{ marginBottom: "10px", color: "#555" }}>
                {filtered.length} labels{belowThreshold > 0 && ` / ${belowThreshold} below threshold`}
            </div>

            {/* Sort */}
            <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                <span>Sort:</span>
                <select value={sortBy} onChange={(e) => onSortByChange(e.target.value as SortBy)} style={{ fontSize: "0.8rem" }}>
                    <option value="position">Position</option>
                    <option value="score">Score</option>
                    <option value="entityGroup">Entity Group</option>
                    <option value="word">Word</option>
                </select>
            </div>

            {/* Entity group filter chips */}
            {allGroups.length > 0 && (
                <div style={{ marginBottom: "8px", display: "flex", gap: "4px", flexWrap: "wrap" }}>
                    {allGroups.map((g) => {
                        const active = entityGroupFilter.size === 0 || entityGroupFilter.has(g);
                        const color = getEntityGroupColor(g);
                        return (
                            <button
                                key={g}
                                onClick={() => onEntityGroupFilterToggle(g)}
                                style={{
                                    padding: "2px 8px",
                                    borderRadius: "12px",
                                    border: `1px solid ${color}`,
                                    backgroundColor: active ? `${color}33` : "transparent",
                                    opacity: active ? 1 : 0.4,
                                    cursor: "pointer",
                                    fontSize: "0.75rem",
                                }}
                            >
                                {g}
                            </button>
                        );
                    })}
                </div>
            )}

            {/* Score threshold slider */}
            <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                <span>Score:</span>
                <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={scoreThreshold}
                    onChange={(e) => onScoreThresholdChange(Number(e.target.value))}
                    style={{ flex: 1 }}
                />
                <span style={{ minWidth: "32px" }}>{scoreThreshold.toFixed(2)}</span>
            </div>

            {/* Word search */}
            <div style={{ marginBottom: "10px" }}>
                <input
                    type="text"
                    placeholder="Search by word..."
                    value={searchWord}
                    onChange={(e) => onSearchWordChange(e.target.value)}
                    style={{ width: "100%", padding: "4px 6px", fontSize: "0.8rem", boxSizing: "border-box" }}
                />
            </div>

            {/* Labels table */}
            <div style={{ overflow: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                    <thead>
                        <tr style={{ borderBottom: "1px solid #ddd", textAlign: "left" }}>
                            <th style={{ padding: "4px" }}>Word</th>
                            <th style={{ padding: "4px" }}>Group</th>
                            <th style={{ padding: "4px" }}>Score</th>
                            <th style={{ padding: "4px" }}>Pos</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sorted.map((label) => {
                            const dimmed = label.labelScore < scoreThreshold;
                            return (
                                <tr
                                    key={`${label.labelStart}-${label.labelEnd}`}
                                    onClick={() => onLabelClick(label)}
                                    style={{
                                        cursor: "pointer",
                                        opacity: dimmed ? 0.4 : 1,
                                        borderBottom: "1px solid #eee",
                                    }}
                                >
                                    <td style={{ padding: "4px" }}>{label.labelWord}</td>
                                    <td style={{ padding: "4px" }}>
                                        <span style={{
                                            backgroundColor: `${getEntityGroupColor(label.labelEntityGroup)}33`,
                                            padding: "1px 4px",
                                            borderRadius: "3px",
                                        }}>
                                            {label.labelEntityGroup ?? "?"}
                                        </span>
                                    </td>
                                    <td style={{ padding: "4px" }}>{label.labelScore.toFixed(2)}</td>
                                    <td style={{ padding: "4px" }}>{label.labelStart}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            </div>
        </div>
    );
};
