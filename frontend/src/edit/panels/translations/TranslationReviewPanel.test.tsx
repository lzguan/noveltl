import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import type {
	Language,
	TranslationOutputChapterDetail,
	TranslationOutputsRead,
	TranslationStageRead,
} from "@/api/models";
import { TranslationReviewPanel } from "./TranslationReviewPanel";

// The review panel provides right-sidebar spot-checking, scroll sync, and accept workflows.
// Mock only HTTP so generated clients, abort handling, and UI state stay real.
afterEach(() => {
	vi.unstubAllGlobals();
});

const defaultStages: TranslationStageRead[] = [
	{
		stageId: "stage-1",
		stageNum: 1,
		action: "translate",
		config: { model: "qwen-plus", target_language: "Japanese" },
	},
];

const defaultLanguages: Language[] = [
	{ languageCode: "en", languageName: "English" },
	{ languageCode: "ja", languageName: "Japanese" },
	{ languageCode: "fr", languageName: "French" },
];

const defaultOutputs: TranslationOutputsRead = {
	selectedStageId: "stage-1",
	stages: [{ stageId: "stage-1", stageNum: 1, action: "translate", chapterCount: 3 }],
	items: [
		{
			chapterId: "ch-1",
			chapterNum: 1,
			chapterTitle: "Dawn",
			batchId: "batch-1",
			batchNum: 0,
			stagedAt: "2026-11-25T00:00:00Z",
			acceptedNovelIds: [],
		},
		{
			chapterId: "ch-2",
			chapterNum: 2,
			chapterTitle: "Dusk",
			batchId: "batch-1",
			batchNum: 0,
			stagedAt: "2026-11-25T00:01:00Z",
			acceptedNovelIds: [],
		},
		{
			chapterId: "ch-3",
			chapterNum: 3,
			chapterTitle: "Midnight",
			batchId: "batch-2",
			batchNum: 1,
			stagedAt: "2026-11-25T00:02:00Z",
			acceptedNovelIds: ["target-1"],
		},
	],
	targetNovels: [
		{
			novelId: "target-1",
			novelTitle: "English Draft",
			languageCode: "en",
			novelType: "translation",
			novelVisibility: 0,
		},
		{
			novelId: "target-2",
			novelTitle: "Japanese Edition",
			languageCode: "ja",
			novelType: "translation",
			novelVisibility: 0,
		},
	],
	lastTargetNovelId: "target-2",
};

const detailsByChapter: Record<string, TranslationOutputChapterDetail> = {
	"ch-1": {
		stageId: "stage-1",
		stageNum: 1,
		chapterId: "ch-1",
		chapterNum: 1,
		chapterTitle: "Dawn",
		batchId: "batch-1",
		batchNum: 0,
		sourceChapterContentId: "cc-1",
		sourceText: "Source line 1\n\nSource line 2",
		translatedText: "Translated line 1\n\nTranslated line 2",
		stagedAt: "2026-11-25T00:00:00Z",
	},
	"ch-2": {
		stageId: "stage-1",
		stageNum: 1,
		chapterId: "ch-2",
		chapterNum: 2,
		chapterTitle: "Dusk",
		batchId: "batch-1",
		batchNum: 0,
		sourceChapterContentId: "cc-2",
		sourceText: "Second source chapter",
		translatedText: "Second translated chapter",
		stagedAt: "2026-11-25T00:01:00Z",
	},
	"ch-3": {
		stageId: "stage-1",
		stageNum: 1,
		chapterId: "ch-3",
		chapterNum: 3,
		chapterTitle: "Midnight",
		batchId: "batch-2",
		batchNum: 1,
		sourceChapterContentId: "cc-3",
		sourceText: "Third source chapter",
		translatedText: "Third translated chapter",
		stagedAt: "2026-11-25T00:02:00Z",
	},
};

function setScrollMetrics(
	element: HTMLElement,
	{
		scrollHeight,
		clientHeight,
		scrollTop = 0,
	}: { scrollHeight: number; clientHeight: number; scrollTop?: number },
) {
	Object.defineProperty(element, "scrollHeight", { value: scrollHeight, configurable: true });
	Object.defineProperty(element, "clientHeight", { value: clientHeight, configurable: true });
	element.scrollTop = scrollTop;
}

function setup({
	currentChapterId = null,
	currentChapterContentId = null,
	editorScrollElement = null,
	sourceWorkId = "work-1",
	stages = defaultStages,
	initialOutputs = defaultOutputs,
	delayChapterId,
}: {
	currentChapterId?: string | null;
	currentChapterContentId?: string | null;
	editorScrollElement?: HTMLElement | null;
	sourceWorkId?: string | null;
	stages?: TranslationStageRead[];
	initialOutputs?: TranslationOutputsRead;
	delayChapterId?: string;
} = {}) {
	let outputsSnapshot: TranslationOutputsRead = structuredClone(initialOutputs);
	const acceptPayloads: unknown[] = [];
	const createNovelPayloads: unknown[] = [];
	const outputListRequests: string[] = [];
	const detailSignals: Record<string, AbortSignal | null | undefined> = {};
	let releaseDelayedDetail: (() => void) | undefined;

	vi.stubGlobal(
		"fetch",
		vi.fn(async (url: string, options?: RequestInit) => {
			const parsed = new URL(url, "http://localhost");
			if (parsed.pathname === "/api/translation-jobs/job-1/outputs") {
				const stageParam = parsed.searchParams.get("stageId");
				outputListRequests.push(`${parsed.pathname}${parsed.search}`);
				return Response.json(
					stageParam
						? { ...outputsSnapshot, selectedStageId: stageParam }
						: outputsSnapshot,
				);
			}
			if (parsed.pathname.startsWith("/api/translation-jobs/job-1/outputs/")) {
				const chapterId = parsed.pathname.split("/").pop() ?? "";
				const stageParam = parsed.searchParams.get("stageId");
				detailSignals[chapterId] = options?.signal;
				if (delayChapterId === chapterId) {
					await new Promise<void>((resolve) => {
						releaseDelayedDetail = resolve;
					});
				}
				const detail = detailsByChapter[chapterId];
				if (!detail) return Response.json({ detail: "Not found" }, { status: 404 });
				return Response.json(
					stageParam && stageParam !== detail.stageId
						? {
								...detail,
								stageId: stageParam,
								stageNum: stageParam === "stage-2" ? 2 : 1,
								translatedText: `[${stageParam}] ${detail.translatedText}`,
							}
						: detail,
				);
			}
			if (parsed.pathname === "/api/languages") {
				return Response.json(defaultLanguages);
			}
			if (parsed.pathname === "/api/novels" && options?.method === "POST") {
				const body: unknown = JSON.parse(String(options.body ?? "{}"));
				createNovelPayloads.push(body);
				const created = {
					novelId: "target-new",
					novelTitle: "Fresh Translation",
					languageCode: "ja",
					novelAuthor: "Translator A",
					novelDescription: null,
					novelType: "translation",
					novelVisibility: 0,
					sourceWorkId: sourceWorkId ?? "work-1",
				};
				return Response.json(created);
			}
			if (
				parsed.pathname === "/api/translation-jobs/job-1/accept" &&
				options?.method === "POST"
			) {
				const body: {
					targetNovelId: string;
					scope: {
						mode: string;
						startChapterNum?: number;
						endChapterNum?: number;
						batchId?: string;
					};
					onExisting?: string;
				} = JSON.parse(String(options.body ?? "{}"));
				acceptPayloads.push(body);
				outputsSnapshot = {
					...outputsSnapshot,
					lastTargetNovelId: body.targetNovelId,
					items: outputsSnapshot.items.map((item) => {
						const matches =
							body.scope.mode === "job" ||
							(body.scope.mode === "batch" && item.batchId === body.scope.batchId) ||
							(body.scope.mode === "range" &&
								item.chapterNum >= (body.scope.startChapterNum ?? 0) &&
								item.chapterNum <= (body.scope.endChapterNum ?? 0));
						if (!matches) return item;
						const prev = item.acceptedNovelIds ?? [];
						return prev.includes(body.targetNovelId)
							? item
							: { ...item, acceptedNovelIds: [body.targetNovelId, ...prev] };
					}),
				};
				return Response.json({
					targetNovelId: body.targetNovelId,
					createdChapters: 1,
					updatedChapters: body.onExisting === "overwrite" ? 1 : 0,
					skippedChapters: body.onExisting === "skip" ? 1 : 0,
					chapterNums: [2],
				});
			}
			return Response.json({ detail: `Unhandled ${parsed.pathname}` }, { status: 404 });
		}),
	);

	const onClose = vi.fn();
	const onAccepted = vi.fn();
	const onSelectChapter = vi.fn();
	const view = render(
		<TranslationReviewPanel
			jobId="job-1"
			stages={stages}
			sourceWorkId={sourceWorkId}
			currentChapterId={currentChapterId}
			currentChapterContentId={currentChapterContentId}
			editorScrollElement={editorScrollElement}
			onSelectChapter={onSelectChapter}
			onClose={onClose}
			onAccepted={onAccepted}
		/>,
	);
	return {
		view,
		acceptPayloads,
		createNovelPayloads,
		outputListRequests,
		detailSignals,
		releaseDelayedDetail: () => releaseDelayedDetail?.(),
		onSelectChapter,
		onClose,
		onAccepted,
	};
}

it("snaps to the currently open editor chapter when staged and collapses header/accept controls by default", async () => {
	setup({ currentChapterId: "ch-2", currentChapterContentId: "cc-2" });
	await screen.findByText("Second translated chapter");
	expect(screen.queryByText("Second source chapter")).not.toBeInTheDocument();
	expect(screen.queryByLabelText("Staged chapter")).not.toBeInTheDocument();
	expect(screen.queryByLabelText("Target novel")).not.toBeInTheDocument();
	expect(screen.queryByText(/Current editor chapter is not staged/)).not.toBeInTheDocument();

	fireEvent.click(screen.getByRole("button", { name: "Toggle review controls" }));
	expect(screen.getByLabelText("Staged chapter")).toHaveValue("ch-2");

	fireEvent.click(screen.getByRole("button", { name: "Show source snapshot" }));
	expect(screen.getByText("Second source chapter")).toBeInTheDocument();
});

it("warns when the open source chapter changed since the job snapshot", async () => {
	setup({ currentChapterId: "ch-2", currentChapterContentId: "cc-newer" });
	await screen.findByText("Second translated chapter");
	expect(screen.getByText(/Source chapter changed since this job ran/)).toBeInTheDocument();
});

it("falls back to the first staged chapter with a note when the open chapter is not staged", async () => {
	setup({ currentChapterId: "ch-missing" });
	await screen.findByText(/Translated line 1/);
	fireEvent.click(screen.getByRole("button", { name: "Toggle review controls" }));
	expect(screen.getByLabelText("Staged chapter")).toHaveValue("ch-1");
	expect(
		screen.getByText(/Current editor chapter is not staged in this job; starting at Ch\. 1\./),
	).toBeInTheDocument();
});

it("switches chapters with prev/next buttons, notifies editor, and aborts stale preview requests", async () => {
	const { detailSignals, releaseDelayedDetail, onSelectChapter } = setup({
		delayChapterId: "ch-1",
	});
	await screen.findByText(/Job job-1 · Review · Ch\. 1/);
	fireEvent.click(screen.getByRole("button", { name: "Toggle review controls" }));
	expect(screen.getByRole("button", { name: "Previous staged chapter" })).toBeDisabled();
	expect(screen.getByRole("button", { name: "Next staged chapter" })).toBeEnabled();

	fireEvent.click(screen.getByRole("button", { name: "Next staged chapter" }));
	expect(onSelectChapter).toHaveBeenCalledWith("ch-2");
	expect(detailSignals["ch-1"]?.aborted).toBe(true);
	await screen.findByText("Second translated chapter");
	expect(screen.getByRole("button", { name: "Previous staged chapter" })).toBeEnabled();

	fireEvent.click(screen.getByRole("button", { name: "Next staged chapter" }));
	expect(onSelectChapter).toHaveBeenCalledWith("ch-3");
	await screen.findByText("Third translated chapter");
	expect(screen.getByRole("button", { name: "Next staged chapter" })).toBeDisabled();

	releaseDelayedDetail();
	expect(screen.getByText("Third translated chapter")).toBeInTheDocument();
});

it("scroll-locks the translated pane with the editor scroll element and supports detaching", async () => {
	const editorScroller = document.createElement("div");
	setScrollMetrics(editorScroller, { scrollHeight: 1200, clientHeight: 200, scrollTop: 0 });

	setup({
		currentChapterId: "ch-2",
		currentChapterContentId: "cc-2",
		editorScrollElement: editorScroller,
	});
	await screen.findByText("Second translated chapter");

	const translatedPane = screen.getByTestId("review-translated-scroll");
	setScrollMetrics(translatedPane, { scrollHeight: 2200, clientHeight: 200, scrollTop: 0 });

	editorScroller.scrollTop = 500;
	fireEvent.scroll(editorScroller);
	expect(translatedPane.scrollTop).toBe(1000);

	// Detaching stops scroll propagation between the panes.
	const syncButton = screen.getByRole("button", { name: "Detach scroll sync" });
	expect(syncButton).toHaveAttribute("aria-pressed", "true");
	fireEvent.click(syncButton);
	expect(screen.getByRole("button", { name: "Sync scroll with source" })).toHaveAttribute(
		"aria-pressed",
		"false",
	);

	editorScroller.scrollTop = 900;
	fireEvent.scroll(editorScroller);
	expect(translatedPane.scrollTop).toBe(1000);
});

it("renders an empty state and back button when no staged outputs are available", async () => {
	const { onClose } = setup({
		initialOutputs: {
			items: [],
			targetNovels: [],
			lastTargetNovelId: null,
		},
	});
	await screen.findByText("No staged translated chapters are available for this job yet.");
	expect(screen.queryByLabelText("Staged chapter")).not.toBeInTheDocument();

	fireEvent.click(screen.getByRole("button", { name: "Jobs" }));
	expect(onClose).toHaveBeenCalledTimes(1);
});

it("creates a translated novel inline with matched target language and selects it", async () => {
	const { createNovelPayloads } = setup({ sourceWorkId: "work-42" });
	await screen.findByText(/Translated line 1/);

	fireEvent.click(screen.getByRole("button", { name: "Toggle accept controls" }));
	fireEvent.click(screen.getByRole("button", { name: "New translated novel" }));
	const languageSelect = await screen.findByLabelText("Language");
	await waitFor(() => expect(languageSelect).toHaveValue("ja"));

	fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Fresh Translation" } });
	fireEvent.change(screen.getByLabelText("Author (optional)"), {
		target: { value: "Translator A" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Create novel" }));

	await waitFor(() => expect(createNovelPayloads).toHaveLength(1));
	expect(createNovelPayloads[0]).toEqual({
		novelTitle: "Fresh Translation",
		languageCode: "ja",
		novelAuthor: "Translator A",
		novelDescription: null,
		novelType: "translation",
		novelVisibility: 0,
		sourceWorkId: "work-42",
	});
	expect(screen.getByLabelText("Target novel")).toHaveValue("target-new");
	expect(screen.getByRole("status")).toHaveTextContent('Created "Fresh Translation".');
});

it("accepts the currently viewed chapter and refreshes outputs metadata", async () => {
	const { acceptPayloads, outputListRequests, onAccepted } = setup({ currentChapterId: "ch-2" });
	await screen.findByText("Second translated chapter");

	fireEvent.click(screen.getByRole("button", { name: "Toggle accept controls" }));
	expect(screen.getByLabelText("Target novel")).toHaveValue("target-2");

	fireEvent.click(screen.getByRole("button", { name: "Accept Ch. 2" }));
	await waitFor(() =>
		expect(screen.getByRole("status")).toHaveTextContent("Created 1, updated 0, skipped 1."),
	);

	expect(acceptPayloads).toEqual([
		{
			targetNovelId: "target-2",
			stageId: "stage-1",
			scope: { mode: "range", startChapterNum: 2, endChapterNum: 2 },
			onExisting: "skip",
		},
	]);
	await waitFor(() => expect(outputListRequests).toHaveLength(2));
	expect(onAccepted).toHaveBeenCalledTimes(1);
	expect(screen.getByText("Accepted")).toBeInTheDocument();
});

it("supports bulk accept for job, batch, and range scopes with skip or overwrite", async () => {
	const { acceptPayloads } = setup();
	await screen.findByText(/Translated line 1/);

	fireEvent.click(screen.getByRole("button", { name: "Toggle accept controls" }));
	fireEvent.click(screen.getByRole("button", { name: "Bulk accept options" }));

	fireEvent.click(screen.getByRole("button", { name: "Accept chapters" }));
	await waitFor(() =>
		expect(screen.getByRole("status")).toHaveTextContent("Created 1, updated 0, skipped 1."),
	);
	expect(acceptPayloads[0]).toEqual({
		targetNovelId: "target-2",
		stageId: "stage-1",
		scope: { mode: "job" },
		onExisting: "skip",
	});

	fireEvent.change(screen.getByLabelText("Scope"), { target: { value: "batch" } });
	fireEvent.change(screen.getByLabelText("Batch"), { target: { value: "batch-2" } });
	fireEvent.change(screen.getByLabelText("Existing chapters"), {
		target: { value: "overwrite" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Accept chapters" }));
	await waitFor(() =>
		expect(screen.getByRole("status")).toHaveTextContent("Created 1, updated 1, skipped 0."),
	);
	expect(acceptPayloads[1]).toEqual({
		targetNovelId: "target-2",
		stageId: "stage-1",
		scope: { mode: "batch", batchId: "batch-2" },
		onExisting: "overwrite",
	});

	fireEvent.change(screen.getByLabelText("Scope"), { target: { value: "range" } });
	fireEvent.change(screen.getByLabelText("Start chapter"), { target: { value: "3" } });
	fireEvent.change(screen.getByLabelText("End chapter"), { target: { value: "2" } });
	expect(screen.getByRole("button", { name: "Accept chapters" })).toBeDisabled();
	expect(screen.getByRole("alert")).toHaveTextContent(/valid non-negative chapter range/);

	fireEvent.change(screen.getByLabelText("Start chapter"), { target: { value: "1" } });
	fireEvent.change(screen.getByLabelText("End chapter"), { target: { value: "2" } });
	fireEvent.click(screen.getByRole("button", { name: "Accept chapters" }));
	await waitFor(() => expect(acceptPayloads).toHaveLength(3));
	expect(acceptPayloads[2]).toEqual({
		targetNovelId: "target-2",
		stageId: "stage-1",
		scope: { mode: "range", startChapterNum: 1, endChapterNum: 2 },
		onExisting: "overwrite",
	});
});

it("shows a stage switcher when multiple stages have staged outputs and forwards stageId", async () => {
	const { acceptPayloads } = setup({
		initialOutputs: {
			...defaultOutputs,
			selectedStageId: "stage-2",
			stages: [
				{ stageId: "stage-1", stageNum: 1, action: "translate", chapterCount: 3 },
				{ stageId: "stage-2", stageNum: 2, action: "translate", chapterCount: 3 },
			],
		},
	});
	await screen.findByText(/\[stage-2\] Translated line 1/);
	fireEvent.click(screen.getByRole("button", { name: "Toggle review controls" }));
	const stageSelect = screen.getByLabelText("Staged stage");
	expect(stageSelect).toHaveValue("stage-2");

	fireEvent.change(stageSelect, { target: { value: "stage-1" } });
	await screen.findByText(/^Translated line 1/);

	fireEvent.click(screen.getByRole("button", { name: "Toggle accept controls" }));
	fireEvent.click(screen.getByRole("button", { name: "Accept Ch. 1" }));
	await waitFor(() => expect(acceptPayloads).toHaveLength(1));
	expect(acceptPayloads[0]).toMatchObject({
		targetNovelId: "target-2",
		stageId: "stage-1",
		scope: { mode: "range", startChapterNum: 1, endChapterNum: 1 },
	});
});
