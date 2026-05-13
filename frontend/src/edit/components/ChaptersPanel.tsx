import type { Chapter } from "@/client";

type ChaptersPanelProps = {
    chapterList: Chapter[];
    activeChapterId: string;
    onSelectChapter: (chapterId: string) => void;
};

export function ChaptersPanel({
    chapterList,
    activeChapterId,
    onSelectChapter,
}: ChaptersPanelProps) {
    return (
        <div className="max-h-72 space-y-2 overflow-auto pr-1">
            {chapterList.map((chapter) => (
                <button
                    key={chapter.chapterId}
                    type="button"
                    onClick={() => onSelectChapter(chapter.chapterId)}
                    className={`flex w-full flex-col rounded-lg border px-3 py-3 text-left ${chapter.chapterId === activeChapterId ? "border-amber-400 bg-amber-50" : "border bg-card"}`}
                >
                    <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Chapter {chapter.chapterNum}</span>
                    <span className="mt-1 text-sm font-medium text-foreground">{chapter.chapterTitle || `Chapter ${chapter.chapterNum}`}</span>
                </button>
            ))}
        </div>
    );
}
