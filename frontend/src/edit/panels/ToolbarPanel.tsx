import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { EditorMode } from "../managers/editorManager";

const MODES: { mode: EditorMode; label: string }[] = [
	{ mode: "view", label: "View" },
	{ mode: "edit", label: "Edit" },
	{ mode: "label", label: "Label" },
];

export function ToolbarPanel({
	novelTitle,
	mode,
	loading,
	onSetMode,
}: {
	novelTitle: string;
	mode: EditorMode;
	loading: boolean;
	onSetMode: (m: EditorMode) => void;
}) {
	return (
		<div className="flex min-w-0 items-center gap-3 border-b p-2">
			<div className="flex shrink-0 gap-1">
				{MODES.map(({ mode: m, label }) => (
					<Button
						key={m}
						variant={mode === m ? "default" : "outline"}
						size="sm"
						onClick={() => onSetMode(m)}
					>
						{label}
					</Button>
				))}
			</div>
			<div className="h-4 w-px shrink-0 bg-border" aria-hidden="true" />
			<h1
				className="min-w-0 flex-1 truncate text-sm font-semibold tracking-tight"
				title={novelTitle}
			>
				{novelTitle}
			</h1>
			{loading && <Skeleton className="h-4 w-16 shrink-0" />}
		</div>
	);
}
