import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { type AddLabelOp } from "../../types/label";

type NewLabelPopoverProps = {
    selectedText: string;
    startPos: number;
    endPos: number;
    anchorRect: DOMRect;
    knownEntityGroups: string[];
    onConfirm: (op: AddLabelOp) => void;
    onClose: () => void;
};

export const NewLabelPopover: React.FC<NewLabelPopoverProps> = ({
    selectedText,
    startPos,
    endPos,
    anchorRect,
    knownEntityGroups,
    onConfirm,
    onClose,
}) => {
    const [entityGroup, setEntityGroup] = useState("");
    const popoverRef = useRef<HTMLDivElement>(null);

    const top = Math.min(anchorRect.bottom + 4, window.innerHeight - 180);
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
        const timer = setTimeout(() => document.addEventListener("mousedown", onClick), 0);
        return () => {
            clearTimeout(timer);
            document.removeEventListener("mousedown", onClick);
        };
    }, [onClose]);

    const handleConfirm = () => {
        onConfirm({
            op: "add",
            startPos,
            endPos,
            word: selectedText,
            entityGroup: entityGroup.trim() || null,
            dirty: true,
            score: 1.0,
        });
    };

    const datalistId = "new-label-entity-groups";

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
                <strong>New Label</strong>
            </div>
            <div style={{ marginBottom: "8px", padding: "4px 8px", backgroundColor: "#f5f5f5", borderRadius: "4px" }}>
                &ldquo;{selectedText}&rdquo;
            </div>
            <div style={{ marginBottom: "8px", color: "#888", fontSize: "0.8rem" }}>
                Position: {startPos} - {endPos}
            </div>
            <div style={{ marginBottom: "10px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    Entity Group:
                    <input
                        type="text"
                        list={datalistId}
                        value={entityGroup}
                        onChange={(e) => setEntityGroup(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") handleConfirm(); }}
                        style={{ flex: 1, padding: "2px 6px" }}
                        autoFocus
                    />
                    <datalist id={datalistId}>
                        {knownEntityGroups.map((g) => (
                            <option key={g} value={g} />
                        ))}
                    </datalist>
                </label>
            </div>
            <div style={{ display: "flex", gap: "6px" }}>
                <button onClick={handleConfirm} style={{ padding: "4px 10px" }}>Confirm</button>
                <button onClick={onClose} style={{ padding: "4px 10px" }}>Cancel</button>
            </div>
        </div>,
        document.body
    );
};
