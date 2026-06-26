import type { ReactNode } from "react";
import {
	ContextMenu,
	ContextMenuContent,
	ContextMenuItem,
	ContextMenuSeparator,
	ContextMenuTrigger,
} from "@/components/ui/context-menu";
import type { EditorLabel } from "./types";

function truncate(text: string, max = 24): string {
	return text.length > max ? `${text.slice(0, max)}…` : text;
}

/**
 * Right-click menu for labeling. Presentational: it renders actions from props
 * and delegates back via callbacks. The trigger wraps `children` (the editor).
 */
export function LabelContextMenu({
	enabled,
	hasSelection,
	canAdd,
	labels,
	onAdd,
	onDelete,
	children,
}: {
	enabled: boolean;
	hasSelection: boolean;
	canAdd: boolean;
	labels: EditorLabel[];
	onAdd: () => void;
	onDelete: (label: EditorLabel) => void;
	children: ReactNode;
}) {
	return (
		<ContextMenu>
			<ContextMenuTrigger asChild disabled={!enabled}>
				{children}
			</ContextMenuTrigger>
			<ContextMenuContent className="min-w-44">
				{hasSelection && (
					<ContextMenuItem disabled={!canAdd} onSelect={() => onAdd()}>
						{canAdd ? "Add label…" : "Add label (no active group)"}
					</ContextMenuItem>
				)}
				{hasSelection && labels.length > 0 && <ContextMenuSeparator />}
				{labels.map((label, i) => (
					<ContextMenuItem
						key={`${label.labelGroupId}-${label.start}-${label.end}-${i}`}
						variant="destructive"
						onSelect={() => onDelete(label)}
					>
						Delete “{truncate(label.word)}” · {label.groupName}
					</ContextMenuItem>
				))}
				{!hasSelection && labels.length === 0 && (
					<ContextMenuItem disabled>No label actions here</ContextMenuItem>
				)}
			</ContextMenuContent>
		</ContextMenu>
	);
}
