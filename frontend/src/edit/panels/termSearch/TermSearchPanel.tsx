import { useRef, useState, type SubmitEvent } from "react";
import {
	searchChapterContentTermChapterContentsChapterContentIdTermSearchGet,
	searchNovelTermNovelsNovelIdTermSearchGet,
} from "@/api/endpoints/default/default";
import type { ChapterTermMatches, NovelTermSearch, TermOccurrencePreview } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { cn } from "@/lib/utils";
import { ChevronRight, LoaderCircleIcon, SearchIcon } from "lucide-react";
import { CCServId, CServId, type ProvChapter } from "../../controller/types/idTypes";

export type GotoText = (
	chapterId: CServId,
	reference: { start: number; end: number; ccServId: CCServId },
) => void;

type Search = { term: string; startChapterNum?: number; endChapterNum?: number };

type Results =
	| { status: "idle" }
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; data: NovelTermSearch; loadingMore: boolean; moreError?: string };

function parseChapterNum(value: string): number | undefined {
	const parsed = Number.parseInt(value.trim(), 10);
	return Number.isNaN(parsed) ? undefined : parsed;
}

async function fetchPage(novelId: string, search: Search, offset: number, signal: AbortSignal) {
	const response = await searchNovelTermNovelsNovelIdTermSearchGet(
		novelId,
		{ ...search, offset },
		{ signal },
	);
	if (response.status !== 200) throw new Error(apiErrorMessage(response.data, "Search failed."));
	return response.data;
}

/** Exact text search across the novel's chapters; results open the matching text in the editor. */
export function TermSearchPanel({
	novelId,
	chapters,
	gotoText,
}: {
	novelId: string;
	chapters: ProvChapter[];
	gotoText: GotoText;
}) {
	const [term, setTerm] = useState("");
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");
	const [search, setSearch] = useState<Search | null>(null);
	const [revision, setRevision] = useState(0);
	const [results, setResults] = useState<Results>({ status: "idle" });
	const controller = useRef<AbortController | null>(null);
	const titles = new Map(chapters.map((chapter) => [chapter.chapterNum, chapter.chapterTitle]));

	async function runSearch(event: SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		if (!term) return;
		const next: Search = {
			term,
			startChapterNum: parseChapterNum(start),
			endChapterNum: parseChapterNum(end),
		};
		controller.current?.abort();
		const current = new AbortController();
		controller.current = current;
		setSearch(next);
		setRevision((value) => value + 1);
		setResults({ status: "loading" });
		try {
			const data = await fetchPage(novelId, next, 0, current.signal);
			if (!current.signal.aborted) setResults({ status: "ready", data, loadingMore: false });
		} catch (error: unknown) {
			if (!current.signal.aborted)
				setResults({ status: "error", message: requestErrorMessage(error) });
		}
	}

	async function loadMore() {
		if (results.status !== "ready" || search === null) return;
		const loaded = results.data;
		const nextOffset = loaded.nextOffset;
		const current = controller.current;
		if (nextOffset === null || current === null) return;
		setResults({ ...results, loadingMore: true, moreError: undefined });
		try {
			const page = await fetchPage(novelId, search, nextOffset, current.signal);
			if (current.signal.aborted) return;
			setResults({
				status: "ready",
				data: { ...page, chapters: [...loaded.chapters, ...page.chapters] },
				loadingMore: false,
			});
		} catch (error: unknown) {
			if (!current.signal.aborted)
				setResults({
					status: "ready",
					data: loaded,
					loadingMore: false,
					moreError: requestErrorMessage(error),
				});
		}
	}

	return (
		<div className="flex h-full min-h-0 flex-col gap-2 p-2">
			<form className="flex flex-col gap-1" onSubmit={(event) => void runSearch(event)}>
				<div className="flex gap-1">
					<Input
						aria-label="Search text"
						placeholder="Find text in this novel"
						className="h-8 min-w-0 text-sm"
						value={term}
						onChange={(event) => setTerm(event.target.value)}
					/>
					<Button type="submit" size="icon-sm" aria-label="Search" disabled={!term}>
						<SearchIcon />
					</Button>
				</div>
				<div className="flex items-center gap-1">
					<Input
						aria-label="From chapter"
						inputMode="numeric"
						placeholder="From"
						className="h-7 min-w-0 text-xs"
						value={start}
						onChange={(event) => setStart(event.target.value)}
					/>
					<span className="text-xs text-muted-foreground">to</span>
					<Input
						aria-label="To chapter"
						inputMode="numeric"
						placeholder="To"
						className="h-7 min-w-0 text-xs"
						value={end}
						onChange={(event) => setEnd(event.target.value)}
					/>
				</div>
			</form>
			<div className="min-h-0 flex-1 overflow-y-auto">
				{results.status === "loading" && (
					<p role="status" className="text-xs text-muted-foreground">
						Searching…
					</p>
				)}
				{results.status === "error" && (
					<p role="alert" className="text-xs text-destructive">
						{results.message}
					</p>
				)}
				{results.status === "ready" && search !== null && (
					<div className="flex flex-col gap-1">
						<p className="text-xs text-muted-foreground">
							{results.data.totalMatches === 0
								? "No results."
								: `${results.data.totalMatches} results in ${results.data.totalChapters} chapters`}
						</p>
						{results.data.chapters.map((chapter) => (
							<ChapterResults
								// A new search remounts the groups so their previews reset.
								key={`${revision}:${chapter.chapterId}`}
								chapter={chapter}
								title={titles.get(chapter.chapterNum)}
								term={search.term}
								gotoText={gotoText}
							/>
						))}
						{results.moreError && (
							<p role="alert" className="text-xs text-destructive">
								{results.moreError}
							</p>
						)}
						{results.data.nextOffset !== null && (
							<Button
								type="button"
								size="xs"
								variant="ghost"
								disabled={results.loadingMore}
								onClick={() => void loadMore()}
							>
								{results.loadingMore ? "Loading…" : "Load more chapters"}
							</Button>
						)}
					</div>
				)}
			</div>
		</div>
	);
}

/** Characters of context shown before a match in a preview row. */
const PREVIEW_LEAD = 8;

type Previews =
	| { status: "idle" }
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; occurrences: TermOccurrencePreview[] };

function ChapterResults({
	chapter,
	title,
	term,
	gotoText,
}: {
	chapter: ChapterTermMatches;
	title: string | undefined;
	term: string;
	gotoText: GotoText;
}) {
	const [open, setOpen] = useState(false);
	const [previews, setPreviews] = useState<Previews>({ status: "idle" });

	async function loadPreviews() {
		setPreviews({ status: "loading" });
		try {
			const response =
				await searchChapterContentTermChapterContentsChapterContentIdTermSearchGet(
					chapter.chapterContentId,
					{ term },
				);
			if (response.status !== 200)
				throw new Error(apiErrorMessage(response.data, "Could not load results."));
			setPreviews({ status: "ready", occurrences: response.data.occurrences });
		} catch (error: unknown) {
			setPreviews({ status: "error", message: requestErrorMessage(error) });
		}
	}

	function jump(start: number) {
		gotoText(CServId(chapter.chapterId), {
			start,
			end: start + term.length,
			ccServId: CCServId(chapter.chapterContentId),
		});
	}

	const label = `Chapter ${chapter.chapterNum}${title ? ` · ${title}` : ""}`;
	return (
		<Collapsible
			open={open}
			onOpenChange={(next) => {
				setOpen(next);
				if (next && (previews.status === "idle" || previews.status === "error"))
					void loadPreviews();
			}}
		>
			<CollapsibleTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					size="xs"
					className="w-full justify-start"
					aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
				>
					<ChevronRight className={cn("transition-transform", open && "rotate-90")} />
					<span className="min-w-0 flex-1 truncate text-left">{label}</span>
					<Badge variant="secondary">{chapter.matchCount}</Badge>
				</Button>
			</CollapsibleTrigger>
			<CollapsibleContent className="flex flex-col pl-5">
				{previews.status === "loading" && (
					<span className="py-1 text-xs text-muted-foreground">
						<LoaderCircleIcon className="inline size-3 animate-spin" /> Loading…
					</span>
				)}
				{previews.status === "error" && (
					<span role="alert" className="py-1 text-xs text-destructive">
						{previews.message}
					</span>
				)}
				{previews.status === "ready" &&
					previews.occurrences.map((occurrence) => {
						const at = occurrence.start - occurrence.previewStart;
						// Rows truncate at the end, so keep the lead-in short enough for the match to show.
						const lead =
							at > PREVIEW_LEAD
								? `…${occurrence.preview.slice(at - PREVIEW_LEAD, at)}`
								: occurrence.preview.slice(0, at);
						return (
							<button
								key={occurrence.start}
								type="button"
								title={occurrence.preview}
								className="truncate rounded px-1 py-0.5 text-left text-xs hover:bg-muted"
								onClick={() => jump(occurrence.start)}
							>
								{lead}
								<mark className="rounded-sm bg-yellow-200 px-0.5 dark:bg-yellow-800">
									{occurrence.preview.slice(at, at + term.length)}
								</mark>
								{occurrence.preview.slice(at + term.length)}
							</button>
						);
					})}
			</CollapsibleContent>
		</Collapsible>
	);
}
