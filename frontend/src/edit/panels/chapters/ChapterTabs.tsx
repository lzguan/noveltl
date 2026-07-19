import { LoaderCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ProvChapter } from "../../controller/types/idTypes";
import type { ChapterTab } from "../../hooks/useChapters";

export function ChapterTabs({
	tabs,
	chapters,
	activeChapterId,
	onActivate,
	onClose,
}: {
	tabs: ChapterTab[];
	chapters: ProvChapter[];
	activeChapterId: ChapterTab["chapterId"] | null;
	onActivate: (chapterId: ChapterTab["chapterId"]) => void;
	onClose: (chapterId: ChapterTab["chapterId"]) => void;
}) {
	if (tabs.length === 0) return null;

	const chaptersById = new Map(chapters.map((chapter) => [chapter.chapterId, chapter]));

	return (
		<div
			role="tablist"
			aria-label="Open chapters"
			className="flex h-9 shrink-0 overflow-x-auto border-b bg-muted/30"
		>
			{tabs.map((tab) => {
				const chapter = chaptersById.get(tab.chapterId);
				const title =
					chapter === undefined
						? "Chapter"
						: `Ch.${chapter.chapterNum}: ${chapter.chapterTitle}`;
				const active = tab.chapterId === activeChapterId;
				return (
					<div
						key={tab.chapterId}
						className="group flex max-w-56 shrink-0 items-center border-r"
					>
						<button
							type="button"
							role="tab"
							aria-selected={active}
							className={`flex h-full min-w-0 flex-1 items-center gap-1.5 px-3 text-left text-xs ${
								active
									? "bg-background text-foreground"
									: "text-muted-foreground hover:bg-background/60 hover:text-foreground"
							}`}
							onClick={() => onActivate(tab.chapterId)}
							title={title}
						>
							{tab.status === "loading" && (
								<LoaderCircle
									className="size-3 shrink-0 animate-spin"
									aria-hidden="true"
								/>
							)}
							<span className="truncate">{title}</span>
						</button>
						<Button
							type="button"
							variant="ghost"
							size="icon-sm"
							className="mr-1 size-6 shrink-0 opacity-60 hover:opacity-100"
							aria-label={`Close ${title}`}
							onClick={() => onClose(tab.chapterId)}
						>
							<X className="size-3" />
						</Button>
					</div>
				);
			})}
		</div>
	);
}
