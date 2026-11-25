import { useState, type ReactNode } from "react";
import { Eye, Pencil, Tag, type LucideIcon } from "lucide-react";
import type { Visibility } from "@/api/models";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { EditorMode } from "../managers/editorManager";
import { getVisibilityMeta, NovelVisibilityDialog } from "./NovelVisibilityDialog";

const MODES: { mode: EditorMode; label: string; icon: LucideIcon }[] = [
	{ mode: "view", label: "View", icon: Eye },
	{ mode: "edit", label: "Edit", icon: Pencil },
	{ mode: "label", label: "Label", icon: Tag },
];

export function ToolbarPanel({
	brand,
	trailing,
	novelId,
	novelTitle,
	novelVisibility,
	publicChapterCount,
	totalChapterCount,
	mode,
	loading,
	onSetMode,
	onVisibilityUpdated,
}: {
	brand?: ReactNode;
	trailing?: ReactNode;
	novelId: string;
	novelTitle: string;
	novelVisibility: Visibility;
	publicChapterCount: number;
	totalChapterCount: number;
	mode: EditorMode;
	loading: boolean;
	onSetMode: (m: EditorMode) => void;
	onVisibilityUpdated: (visibility: Visibility) => void;
}) {
	const [showVisibility, setShowVisibility] = useState(false);
	const visibilityMeta = getVisibilityMeta(novelVisibility);
	const VisibilityIcon = visibilityMeta.icon;

	return (
		<header className="flex h-11 min-w-0 shrink-0 items-center gap-2 border-b bg-background/95 px-3 backdrop-blur">
			{brand && (
				<>
					{brand}
					<span className="shrink-0 text-sm text-muted-foreground/50" aria-hidden="true">
						/
					</span>
				</>
			)}
			<h1
				className="min-w-0 flex-1 truncate text-sm font-medium tracking-tight"
				title={novelTitle}
			>
				{novelTitle}
			</h1>
			{loading && <Skeleton className="h-4 w-16 shrink-0" />}
			<Button
				type="button"
				variant="outline"
				size="sm"
				className="h-7 shrink-0 gap-1.5 px-2.5 text-xs font-medium"
				aria-label={`Novel visibility: ${visibilityMeta.label}`}
				title="Change novel visibility"
				onClick={() => setShowVisibility(true)}
			>
				<VisibilityIcon className="size-3" aria-hidden="true" />
				{visibilityMeta.label}
			</Button>
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
								"inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-medium",
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
			{trailing && (
				<>
					<div className="h-4 w-px shrink-0 bg-border" aria-hidden="true" />
					{trailing}
				</>
			)}
			{showVisibility && (
				<NovelVisibilityDialog
					novelId={novelId}
					currentVisibility={novelVisibility}
					publicChapterCount={publicChapterCount}
					totalChapterCount={totalChapterCount}
					onUpdated={onVisibilityUpdated}
					onClose={() => setShowVisibility(false)}
				/>
			)}
		</header>
	);
}
