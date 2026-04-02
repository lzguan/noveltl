import React, { useState, useEffect } from "react";
import { updateRevisionText, getRevisionText } from "../../api/novels";
import { diffToTextOps } from "./diffToTextOps";
import { AxiosError } from "axios";

type InlineTextEditorProps = {
    text: string;
    revisionTextId: string;
    revisionId: string;
    onSaveSuccess: (newText: string, newRevisionTextId: string) => void;
    onSaveError: (message: string) => void;
    loading: boolean;
};

export const InlineTextEditor: React.FC<InlineTextEditorProps> = ({
    text,
    revisionTextId,
    revisionId,
    onSaveSuccess,
    onSaveError,
    loading,
}) => {
    const [editedText, setEditedText] = useState(text);
    const [saving, setSaving] = useState(false);

    // Re-sync local text when the server text changes (new revisionTextId)
    useEffect(() => {
        setEditedText(text);
    }, [revisionTextId, text]);

    const isDirty = editedText !== text;

    const handleSave = async () => {
        const ops = diffToTextOps(text, editedText);
        if (ops.length === 0) return;

        setSaving(true);
        try {
            await updateRevisionText(revisionId, {
                textOps: ops,
                revisionTextId,
            });
            // Re-fetch to get the new revisionTextId and content
            const fresh = await getRevisionText(revisionId);
            onSaveSuccess(fresh.revisionTextContent, fresh.revisionTextId);
        } catch (err) {
            if (err instanceof AxiosError && err.response?.status === 409) {
                // Stale revision text — refresh and notify
                try {
                    const fresh = await getRevisionText(revisionId);
                    onSaveSuccess(fresh.revisionTextContent, fresh.revisionTextId);
                } catch { /* refresh failed, parent state stays as-is */ }
                onSaveError("Text was modified elsewhere. Your changes could not be saved. The text has been refreshed.");
            } else {
                onSaveError("Failed to save text changes.");
            }
        } finally {
            setSaving(false);
        }
    };

    const handleDiscard = () => {
        setEditedText(text);
    };

    if (loading) {
        return <div style={{ padding: "20px", color: "#888" }}>Loading...</div>;
    }

    return (
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <div style={{ padding: "8px 16px", borderBottom: "1px solid #ddd", display: "flex", gap: "8px", alignItems: "center" }}>
                <button
                    onClick={() => void handleSave()}
                    disabled={!isDirty || saving}
                    style={{
                        padding: "4px 14px",
                        backgroundColor: isDirty ? "#4a90d9" : "#ccc",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        cursor: isDirty && !saving ? "pointer" : "not-allowed",
                        fontSize: "0.85rem",
                    }}
                >
                    {saving ? "Saving..." : "Save"}
                </button>
                <button
                    onClick={handleDiscard}
                    disabled={!isDirty || saving}
                    style={{
                        padding: "4px 14px",
                        backgroundColor: "transparent",
                        border: "1px solid #ccc",
                        borderRadius: "4px",
                        cursor: isDirty && !saving ? "pointer" : "not-allowed",
                        fontSize: "0.85rem",
                        color: isDirty ? "#333" : "#999",
                    }}
                >
                    Discard
                </button>
                {isDirty && (
                    <span style={{ fontSize: "0.8rem", color: "#888" }}>Unsaved changes</span>
                )}
            </div>
            <textarea
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                disabled={saving}
                style={{
                    flex: 1,
                    resize: "none",
                    border: "none",
                    outline: "none",
                    padding: "20px",
                    whiteSpace: "pre-wrap",
                    textAlign: "left",
                    fontFamily: "serif",
                    fontSize: "1.05rem",
                    lineHeight: 1.8,
                    backgroundColor: saving ? "#f9f9f9" : "#fff",
                }}
            />
        </div>
    );
};
