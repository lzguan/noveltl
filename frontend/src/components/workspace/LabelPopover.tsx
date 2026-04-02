import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { type Label, type UpdateLabelOp, type DeleteLabelOp } from "../../types/label";

type LabelPopoverProps = {
    label: Label;
    anchorRect: DOMRect;
    knownEntityGroups: string[];
    onSave: (op: UpdateLabelOp) => void;
    onDelete: (op: DeleteLabelOp) => void;
    onClose: () => void;
};

export const LabelPopover: React.FC<LabelPopoverProps> = ({
    label,
    anchorRect,
    knownEntityGroups,
    onSave,
    onDelete,
    onClose,
}) => {
    const [entityGroup, setEntityGroup] = useState(label.labelEntityGroup ?? "");
    const [dirty, setDirty] = useState(label.labelDirty);
    const popoverRef = useRef<HTMLDivElement>(null);

    // Position with viewport clamping
    const top = Math.min(anchorRect.bottom + 4, window.innerHeight - 220);
    const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - 280));

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [onClose]);

    useEffect(() => {
        const onClick = (e: MouseEvent) => {
            if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
                onClose();
            }
        };
        // Delay to avoid the opening click triggering close
        const timer = setTimeout(() => document.addEventListener("mousedown", onClick), 0);
        return () => {
            clearTimeout(timer);
            document.removeEventListener("mousedown", onClick);
        };
    }, [onClose]);

    const handleSave = () => {
        const op: UpdateLabelOp = {
            op: "update",
            startPos: label.labelStart,
            endPos: label.labelEnd,
            word: label.labelWord,
        };
        const newGroup = entityGroup.trim() || null;
        if (newGroup !== label.labelEntityGroup) op.entityGroup = newGroup;
        if (dirty !== label.labelDirty) op.dirty = dirty;
        onSave(op);
    };

    const handleDelete = () => {
        onDelete({
            op: "delete",
            startPos: label.labelStart,
            endPos: label.labelEnd,
            word: label.labelWord,
        });
    };

    const datalistId = "known-entity-groups";

    return createPortal(
        <div
            ref={popoverRef}
            style={{
                position: "fixed",
                top,
                left,
                zIndex: 1100,
                background: "#fff",
                border: "1px solid #ccc",
                borderRadius: "6px",
                padding: "12px",
                boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                minWidth: "240px",
                fontSize: "0.9rem",
            }}
        >
            <div style={{ marginBottom: "8px" }}>
                <strong>Word:</strong> {label.labelWord}
            </div>
            <div style={{ marginBottom: "8px", color: "#888", fontSize: "0.8rem" }}>
                Position: {label.labelStart} - {label.labelEnd}
            </div>
            <div style={{ marginBottom: "8px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    Entity Group:
                    <input
                        type="text"
                        list={datalistId}
                        value={entityGroup}
                        onChange={(e) => setEntityGroup(e.target.value)}
                        style={{ flex: 1, padding: "2px 6px" }}
                    />
                    <datalist id={datalistId}>
                        {knownEntityGroups.map((g) => (
                            <option key={g} value={g} />
                        ))}
                    </datalist>
                </label>
            </div>
            <div style={{ marginBottom: "10px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <input type="checkbox" checked={dirty} onChange={(e) => setDirty(e.target.checked)} />
                    Dirty
                </label>
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
                <button onClick={handleSave} style={{ padding: "4px 10px" }}>Save</button>
                <button onClick={handleDelete} style={{ padding: "4px 10px", color: "red" }}>Delete</button>
                <button onClick={onClose} style={{ padding: "4px 10px" }}>Cancel</button>
            </div>
        </div>,
        document.body
    );
};
