import React, { useState } from "react";
import { type AutoLabelMeta, type AutoLabel } from "../../types/autolabel";
import { type LabelGroup, type CreateLabelDataByAutoLabelStatus } from "../../types/label";
import { LabelGroupSelector } from "./LabelGroupSelector";

type NerPanelProps = {
    labelGroups: LabelGroup[];
    selectedGroupId: string | null;
    onGroupChange: (groupId: string | null) => void;
    autoLabelMetas: AutoLabelMeta[];
    selectedAutoLabelId: string | null;
    onAutoLabelSelect: (autoLabelId: string) => void;
    autoLabelMeta: AutoLabelMeta | null;
    autoLabelPreview: AutoLabel | null;
    showPreview: boolean;
    onTogglePreview: (show: boolean) => void;
    nerModelName: string;
    onNerModelNameChange: (value: string) => void;
    nerModelParams: string;
    onNerModelParamsChange: (value: string) => void;
    isRunningNer: boolean;
    onRunNer: () => void;
    onLoadIntoGroup: () => void;
    loadStatus: CreateLabelDataByAutoLabelStatus | null;
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
    pending: { label: "Pending...", color: "#e67e22" },
    processing: { label: "Processing...", color: "#3498db" },
    done: { label: "Done", color: "#27ae60" },
    failed: { label: "Failed", color: "#e74c3c" },
};

export const NerPanel: React.FC<NerPanelProps> = ({
    labelGroups,
    selectedGroupId,
    onGroupChange,
    autoLabelMetas,
    selectedAutoLabelId,
    onAutoLabelSelect,
    autoLabelMeta,
    autoLabelPreview,
    showPreview,
    onTogglePreview,
    nerModelName,
    onNerModelNameChange,
    nerModelParams,
    onNerModelParamsChange,
    isRunningNer,
    onRunNer,
    onLoadIntoGroup,
    loadStatus,
}) => {
    const [paramsExpanded, setParamsExpanded] = useState(false);

    const statusInfo = autoLabelMeta ? STATUS_LABELS[autoLabelMeta.autoLabelStatus] : null;
    const isPolling = autoLabelMeta?.autoLabelStatus === "pending" || autoLabelMeta?.autoLabelStatus === "processing";
    const isDone = autoLabelMeta?.autoLabelStatus === "done";

    // Dedup guard: disable Run NER when any existing auto-label matches current form
    const isDuplicate = autoLabelMetas.some((m) =>
        m.autoLabelModelName === nerModelName.trim() &&
        (() => {
            try {
                const parsed = JSON.parse(nerModelParams);
                return JSON.stringify(parsed) === JSON.stringify(m.autoLabelModelParams);
            } catch {
                return false;
            }
        })()
    );

    return (
        <div style={{ fontSize: "0.85rem" }}>
            <LabelGroupSelector
                labelGroups={labelGroups}
                selectedGroupId={selectedGroupId}
                onGroupChange={onGroupChange}
            />
            <div style={{ padding: "12px" }}>

            {/* Auto-label selector */}
            {autoLabelMetas.length > 0 && (
                <div style={{ marginBottom: "10px" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ fontWeight: 600 }}>NER Run:</span>
                        <select
                            value={selectedAutoLabelId ?? ""}
                            onChange={(e) => onAutoLabelSelect(e.target.value)}
                            style={{ flex: 1, padding: "2px 4px", fontSize: "0.85rem" }}
                        >
                            {autoLabelMetas.map((m) => {
                                const status = STATUS_LABELS[m.autoLabelStatus];
                                return (
                                    <option key={m.autoLabelId} value={m.autoLabelId}>
                                        {m.autoLabelModelName} — {status?.label ?? m.autoLabelStatus}
                                    </option>
                                );
                            })}
                        </select>
                    </label>
                </div>
            )}

            {/* Status display */}
            {autoLabelMeta && statusInfo && (
                <div style={{ marginBottom: "10px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ fontWeight: 600 }}>Status:</span>
                        <span style={{ color: statusInfo.color }}>
                            {isPolling && <span style={{ marginRight: "4px" }}>&#x21bb;</span>}
                            {statusInfo.label}
                        </span>
                    </div>
                    {autoLabelMeta.autoLabelStatus === "failed" && autoLabelMeta.autoLabelMessage && (
                        <div style={{ color: "#e74c3c", marginTop: "4px", fontSize: "0.8rem" }}>
                            {autoLabelMeta.autoLabelMessage}
                        </div>
                    )}
                    <div style={{ color: "#888", fontSize: "0.75rem", marginTop: "4px" }}>
                        Model: {autoLabelMeta.autoLabelModelName}
                    </div>
                </div>
            )}

            {/* Run NER form */}
            <div style={{ marginBottom: "12px" }}>
                <div style={{ marginBottom: "6px" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        Model:
                        <input
                            type="text"
                            value={nerModelName}
                            onChange={(e) => onNerModelNameChange(e.target.value)}
                            placeholder="e.g. cluener"
                            style={{ flex: 1, padding: "2px 6px" }}
                        />
                    </label>
                </div>
                <div style={{ marginBottom: "6px" }}>
                    <button
                        onClick={() => setParamsExpanded(!paramsExpanded)}
                        style={{ background: "none", border: "none", cursor: "pointer", color: "#4a90d9", padding: 0, fontSize: "0.8rem" }}
                    >
                        {paramsExpanded ? "Hide" : "Show"} params
                    </button>
                    {paramsExpanded && (
                        <textarea
                            value={nerModelParams}
                            onChange={(e) => onNerModelParamsChange(e.target.value)}
                            placeholder='{"key": "value"}'
                            style={{ width: "100%", minHeight: "60px", marginTop: "4px", fontSize: "0.8rem", fontFamily: "monospace", boxSizing: "border-box" }}
                        />
                    )}
                </div>
                <button
                    onClick={onRunNer}
                    disabled={isRunningNer || !nerModelName.trim() || isDuplicate || isPolling}
                    style={{
                        padding: "6px 14px",
                        backgroundColor: "#4a90d9",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        cursor: isRunningNer || !nerModelName.trim() || isDuplicate || isPolling ? "not-allowed" : "pointer",
                        opacity: isRunningNer || !nerModelName.trim() || isDuplicate || isPolling ? 0.5 : 1,
                    }}
                >
                    {isRunningNer ? "Submitting..." : "Run NER"}
                </button>
                {isDuplicate && (
                    <span style={{ marginLeft: "8px", color: "#888", fontSize: "0.75rem" }}>
                        Already run with these params
                    </span>
                )}
            </div>

            {/* Preview toggle */}
            {isDone && (
                <div style={{ marginBottom: "8px" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <input
                            type="checkbox"
                            checked={showPreview}
                            onChange={(e) => onTogglePreview(e.target.checked)}
                        />
                        Preview NER results{autoLabelPreview ? ` (${autoLabelPreview.autoLabelData?.length ?? 0} labels)` : ""}
                    </label>
                </div>
            )}

            {/* Load into group button */}
            {isDone && selectedGroupId !== null && (
                <div style={{ marginBottom: "8px" }}>
                    <button
                        onClick={onLoadIntoGroup}
                        style={{
                            padding: "6px 14px",
                            backgroundColor: "#27ae60",
                            color: "#fff",
                            border: "none",
                            borderRadius: "4px",
                            cursor: "pointer",
                        }}
                    >
                        Load into group
                    </button>
                </div>
            )}

            {/* Load result summary */}
            {loadStatus && (
                <div style={{ marginTop: "8px", padding: "8px", backgroundColor: "#f5f5f5", borderRadius: "4px", fontSize: "0.8rem" }}>
                    <div style={{ color: "#27ae60" }}>
                        Loaded: {loadStatus.success.length} revision(s)
                    </div>
                    {loadStatus.errors.length > 0 && (
                        <div style={{ color: "#e74c3c", marginTop: "4px" }}>
                            Errors: {loadStatus.errors.map(([revId, msg]) => `Rev ${revId}: ${msg}`).join("; ")}
                        </div>
                    )}
                </div>
            )}
            </div>
        </div>
    );
};
