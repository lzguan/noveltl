import { Button } from "@/components/ui/button";
import type { Role } from "@/client";

type ModePanelProps = {
    mode: "edit" | "label" | "view";
    editorActive: boolean;
    textLength: number;
    selectionStart: number;
    selectionEnd: number;
    selectedText: string;
    role: Role;
    onSwitchMode: (mode: "edit" | "label" | "view") => void;
};

export function ModePanel({
    mode,
    editorActive,
    textLength,
    selectionStart,
    selectionEnd,
    selectedText,
    role,
    onSwitchMode,
}: ModePanelProps) {
    return (
        <div className="space-y-4 pt-3">
            <div className="grid grid-cols-3 gap-2">
                <Button type="button" variant={mode === "view" ? "default" : "secondary"} onClick={() => onSwitchMode("view")}>
                    View
                </Button>
                <Button type="button" variant={mode === "edit" ? "default" : "secondary"} onClick={() => onSwitchMode("edit")} disabled={role === "viewer"}>
                    Edit
                </Button>
                <Button type="button" variant={mode === "label" ? "default" : "secondary"} onClick={() => onSwitchMode("label")}>
                    Label
                </Button>
            </div>
            <div className="rounded-lg border bg-muted p-3 text-sm text-foreground">
                <div>{editorActive ? "Editor focused" : "Editor blurred"}</div>
                <div>{textLength} characters</div>
                <div>Selection [{selectionStart}, {selectionEnd})</div>
                <div className="truncate">{selectedText || "No selected text"}</div>
            </div>
        </div>
    );
}
