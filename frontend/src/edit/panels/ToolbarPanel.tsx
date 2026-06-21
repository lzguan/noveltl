import { useEffect, useState } from "react";
import { Effect } from "effect";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { EditorManager, EditorMode } from "../managers/editorManager";

const MODES: { mode: EditorMode; label: string }[] = [
	{ mode: "view", label: "View" },
	{ mode: "edit", label: "Edit" },
	{ mode: "label", label: "Label" },
];

export function ToolbarPanel({ editorManager }: { editorManager: EditorManager }) {
	const [mode, setMode] = useState(editorManager.getters.mode());
	const [isLoading, setIsLoading] = useState(editorManager.getters.isLoading());

	useEffect(() => {
		const unsub = editorManager.subscribe(() => {
			setMode(editorManager.getters.mode());
			setIsLoading(editorManager.getters.isLoading());
			return Effect.succeed(void 0);
		});
		return unsub;
	}, [editorManager]);

	return (
		<div className="flex items-center gap-2 p-2 border-b">
			<div className="flex gap-1">
				{MODES.map(({ mode: m, label }) => (
					<Button
						key={m}
						variant={mode === m ? "default" : "outline"}
						size="sm"
						onClick={() => editorManager.switchMode(m)}
					>
						{label}
					</Button>
				))}
			</div>
			<div className="flex-1" />
			{isLoading && <Skeleton className="h-4 w-16" />}
		</div>
	);
}
