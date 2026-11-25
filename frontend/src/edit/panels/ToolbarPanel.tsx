import { Eye, Pencil, Tag, type LucideIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { EditorMode } from "../managers/editorManager";

const MODES: { mode: EditorMode; label: string; icon: LucideIcon }[] = [
	{ mode: "view", label: "View", icon: Eye },
	{ mode: "edit", label: "Edit", icon: Pencil },
	{ mode: "label", label: "Label", icon: Tag },
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
		<div className="flex min-w-0 items-center gap-3 border-b px-3 py-1.5">
			<h1
				className="min-w-0 flex-1 truncate text-sm font-semibold tracking-tight"
				title={novelTitle}
			>
				{novelTitle}
			</h1>
			{loading && <Skeleton className="h-4 w-16 shrink-0" />}
			<div
				role="group"
				aria-label="Editor mode"
				className="inline-flex shrink-0 items-center rounded-md border bg-muted p-0.5"
			>
				{MODES.map(({ mode: m, label, icon: Icon }) => {
					const active = mode === m;
					return (
						<button
							key={m}
							type="button"
							aria-pressed={active}
							className={cn(
								"inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-medium transition-colors",
								active
									? "bg-background text-foreground shadow-xs"
									: "text-muted-foreground hover:text-foreground",
							)}
							onClick={() => onSetMode(m)}
						>
							<Icon className="size-3" aria-hidden="true" />
							{label}
						</button>
					);
				})}
			</div>
		</div>
	);
}
