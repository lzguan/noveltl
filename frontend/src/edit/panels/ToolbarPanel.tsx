import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { EditorMode } from "../managers/editorManager";

const MODES: { mode: EditorMode; label: string }[] = [
	{ mode: "view", label: "View" },
	{ mode: "edit", label: "Edit" },
	{ mode: "label", label: "Label" },
];

export function ToolbarPanel({
	mode,
	loading,
	onSetMode,
}: {
	mode: EditorMode;
	loading: boolean;
	onSetMode: (m: EditorMode) => void;
}) {
	return (
		<div className="flex items-center gap-2 p-2 border-b">
			<div className="flex gap-1">
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
			<div className="flex-1" />
			{loading && <Skeleton className="h-4 w-16" />}
		</div>
	);
}
