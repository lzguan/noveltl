import { useState } from "react";
import { type LabelGroup, type CreateLabelGroup } from "../../types/label";
import { createLabelGroup } from "../../api/labels";

type LabelGroupSelectorProps = {
    labelGroups: LabelGroup[];
    selectedGroupId: string | null;
    onGroupChange: (groupId: string | null) => void;
    novelId?: string;
    onGroupCreated?: (labelGroup: LabelGroup) => void;
};

export const LabelGroupSelector: React.FC<LabelGroupSelectorProps> = ({
    labelGroups,
    selectedGroupId,
    onGroupChange,
    novelId,
    onGroupCreated,
}) => {
    const [newGroupName, setNewGroupName] = useState("");
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);

    const handleCreateGroup = async () => {
        const name = newGroupName.trim();
        if (!name || !onGroupCreated || !novelId) return;
        setIsCreating(true);
        setCreateError(null);
        try {
            const request: CreateLabelGroup = { labelGroupName: name, novelId };
            const created = await createLabelGroup(request);
            onGroupCreated(created);
            setNewGroupName("");
        } catch {
            setCreateError("Failed to create label group");
        } finally {
            setIsCreating(false);
        }
    };

    return (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 12px", borderBottom: "1px solid #eee", flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.85rem" }}>
                Group:
                <select
                    value={selectedGroupId ?? ""}
                    onChange={(e) => onGroupChange(e.target.value || null)}
                    style={{ padding: "2px 4px", fontSize: "0.85rem" }}
                >
                    <option value="">-- Select --</option>
                    {labelGroups.map((lg) => (
                        <option key={lg.labelGroupId} value={lg.labelGroupId}>
                            {lg.labelGroupName}
                        </option>
                    ))}
                </select>
            </label>

            {onGroupCreated && novelId && (
                <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                    <input
                        type="text"
                        placeholder="New group name"
                        value={newGroupName}
                        onChange={(e) => setNewGroupName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") void handleCreateGroup(); }}
                        style={{ width: "120px", padding: "2px 6px", fontSize: "0.85rem" }}
                    />
                    <button onClick={() => void handleCreateGroup()} disabled={isCreating || !newGroupName.trim()}>
                        {isCreating ? "..." : "+"}
                    </button>
                    {createError && <span style={{ color: "red", fontSize: "0.8rem" }}>{createError}</span>}
                </div>
            )}
        </div>
    );
};
