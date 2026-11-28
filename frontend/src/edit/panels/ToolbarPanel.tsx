import { memo, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, Eye, Pencil, Tag, Upload, type LucideIcon } from "lucide-react";
import type { Visibility } from "@/api/models";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { EditorMode } from "../managers/editorManager";
import { getVisibilityMeta, NovelVisibilityDialog } from "./NovelVisibilityDialog";
import { PublishNovelDialog } from "./PublishNovelDialog";

const MODES: { mode: EditorMode; label: string; icon: LucideIcon }[] = [
	{ mode: "view", label: "View", icon: Eye },
	{ mode: "edit", label: "Edit", icon: Pencil },
	{ mode: "label", label: "Label", icon: Tag },
];

export const ToolbarPanel = memo(function ToolbarPanel({
	brand,
	trailing,
	novelId,
	novelTitle,
	novelVisibility,
	canPublish = false,
	publicChapterCount,
	totalChapterCount,
	currentChapterNum,
	hasPreviousChapter,
	hasNextChapter,
	mode,
	loading,
	onPreviousChapter,
	onNextChapter,
	onSetMode,
	onVisibilityUpdated,
}: {
	brand?: ReactNode;
	trailing?: ReactNode;
	novelId: string;
	novelTitle: string;
	novelVisibility: Visibility;
	canPublish?: boolean;
	publicChapterCount: number;
	totalChapterCount: number;
	currentChapterNum: number | null;
	hasPreviousChapter: boolean;
	hasNextChapter: boolean;
	mode: EditorMode;
	loading: boolean;
	onPreviousChapter: () => void;
	onNextChapter: () => void;
	onSetMode: (m: EditorMode) => void;
	onVisibilityUpdated: (visibility: Visibility) => void;
}) {
	const [showVisibility, setShowVisibility] = useState(false);
	const [showPublish, setShowPublish] = useState(false);
	const visibilityMeta = getVisibilityMeta(novelVisibility);
	const VisibilityIcon = visibilityMeta.icon;
	const canGoPrevious = currentChapterNum !== null && hasPreviousChapter;
	const canGoNext = currentChapterNum !== null && hasNextChapter;

	return (
		<header className="grid h-11 min-w-0 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-2 border-b bg-background/95 px-3 backdrop-blur">
			<div className="flex min-w-0 items-center gap-2">
				{brand && (
					<>
						{brand}
						<span
							className="shrink-0 text-sm text-muted-foreground/50"
							aria-hidden="true"
						>
							/
						</span>
					</>
				)}
				<h1
					className="min-w-0 truncate text-sm font-medium tracking-tight"
					title={novelTitle}
				>
					{novelTitle}
				</h1>
				{loading && <Skeleton className="h-4 w-16 shrink-0" />}
			</div>
			<div
				role="group"
				aria-label="Chapter navigation"
				className="inline-flex h-7 shrink-0 items-center justify-self-center rounded-md border bg-background shadow-xs"
			>
				<Button
					type="button"
					variant="ghost"
					size="icon-xs"
					className="h-full w-7 rounded-r-none border-r"
					aria-label="Previous chapter"
					title="Previous chapter"
					disabled={!canGoPrevious}
					onClick={onPreviousChapter}
				>
					<ChevronLeft className="size-3.5" aria-hidden="true" />
				</Button>
				<span
					className={cn(
						"min-w-14 px-2 text-center text-xs font-medium tabular-nums select-none",
						currentChapterNum === null && "text-muted-foreground",
					)}
					title={
						currentChapterNum === null
							? "No chapter open"
							: `Chapter ${currentChapterNum}`
					}
				>
					{currentChapterNum === null ? "—" : `Ch. ${currentChapterNum}`}
				</span>
				<Button
					type="button"
					variant="ghost"
					size="icon-xs"
					className="h-full w-7 rounded-l-none border-l"
					aria-label="Next chapter"
					title="Next chapter"
					disabled={!canGoNext}
					onClick={onNextChapter}
				>
					<ChevronRight className="size-3.5" aria-hidden="true" />
				</Button>
			</div>
			<div className="flex min-w-0 items-center justify-end gap-2">
				{canPublish && (
					<Button
						type="button"
						variant="outline"
						size="sm"
						className="h-7 shrink-0 gap-1.5 px-2.5 text-xs font-medium"
						onClick={() => setShowPublish(true)}
					>
						<Upload className="size-3" aria-hidden="true" />
						Publish
					</Button>
				)}
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
			</div>
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
			{canPublish && showPublish && (
				<PublishNovelDialog
					novelId={novelId}
					novelTitle={novelTitle}
					onClose={() => setShowPublish(false)}
				/>
			)}
		</header>
	);
});
