import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import { TranslationsPanel } from "./TranslationsPanel";
import type { TranslationJobSummary, TranslationBatchDetail } from "@/api/models";

const job: TranslationJobSummary = {
	jobId: "job-1",
	config: {},
	stages: [{ stageId: "stage-1", stageNum: 0, action: "translate", config: {} }],
	progress: {
		totalTasks: 6,
		completedTasks: 1,
		totalBatches: 6,
		completedBatches: 1,
		activeBatches: 1,
		failedBatches: 1,
		cancelledBatches: 0,
		startableBatches: 3,
		resumableBatches: 4,
		retryableBatches: 5,
	},
};
const batches: TranslationBatchDetail[] = Array.from({ length: 6 }, (_, index) => ({
	batchId: `batch-${index}`,
	batchNum: index,
	initialFileId: null,
	tasks: [
		{
			taskId: `task-${index}`,
			batchId: `batch-${index}`,
			stageId: "stage-1",
			status: index === 0 ? "complete" : "ready",
			failedAt: null,
			error: null,
			claimExpiresAt: null,
			inputFileId: null,
			outputFileId: null,
		},
	],
}));
// The viewer serves operators with persisted progress and scoped controls. Mock
// only HTTP to simulate queue failures and changing snapshots; keep clients/UI real.
afterEach(() => {
	vi.unstubAllGlobals();
	vi.useRealTimers();
});
function setup() {
	const reads: string[] = [];
	const posts: string[] = [];
	let readFails = false;
	let release: (() => void) | undefined;
	vi.stubGlobal(
		"fetch",
		vi.fn(async (url: string, options?: RequestInit) => {
			const parsed = new URL(url, "http://localhost");
			if (options?.method === "POST") {
				posts.push(parsed.pathname);
				await new Promise<void>((resolve) => {
					release = resolve;
				});
				return Response.json({
					affectedBatchIds: ["batch-1"],
					dispatchedTaskIds: [],
					dispatchFailedTaskIds: ["task-1"],
				});
			}
			reads.push(url);
			if (readFails) return Response.json({ detail: "Read unavailable" }, { status: 503 });
			if (parsed.pathname.endsWith("/batches")) {
				const offset = Number(parsed.searchParams.get("offset"));
				return Response.json({
					job,
					items: batches.slice(offset, offset + 5),
					total: 6,
					observedAt: "2026-09-18T00:00:00Z",
				});
			}
			return Response.json({
				items: parsed.searchParams.get("offset") === "5" ? [] : [job],
				total: 6,
			});
		}),
	);
	const view = render(<TranslationsPanel novelId="novel-1" chapterNumbers={[1, 2]} />);
	return {
		view,
		reads,
		posts,
		failReads: () => {
			readFails = true;
		},
		release: () => release?.(),
	};
}
it("loads paged history and fetches batches only when their dialog is open", async () => {
	const { reads } = setup();
	await screen.findByRole("heading", { name: "Job job-1" });
	expect(reads.every((url) => !url.includes("/batches"))).toBe(true);
	expect(reads[0]).toContain("novelId=novel-1");
	fireEvent.click(screen.getByRole("button", { name: "Show details for job job-1" }));
	await screen.findByRole("heading", { name: "Batch 5" });
	const dialog = within(screen.getByRole("dialog"));
	expect(dialog.queryByRole("heading", { name: "Batch 6" })).not.toBeInTheDocument();
	fireEvent.click(dialog.getByRole("button", { name: "Next" }));
	await dialog.findByRole("heading", { name: "Batch 6" });
	expect(dialog.queryByRole("heading", { name: "Batch 1" })).not.toBeInTheDocument();
	expect(reads.some((url) => url.includes("/batches?offset=5"))).toBe(true);
	fireEvent.click(dialog.getByRole("button", { name: "Close" }));
	fireEvent.click(screen.getByRole("button", { name: "Next" }));
	await screen.findByText("No jobs on this page.");
	expect(reads.some((url) => url.includes("novelId=novel-1&offset=5"))).toBe(true);
});
it("scopes batch controls, prevents duplicate requests, and reports partial dispatch failures", async () => {
	const { posts, release } = setup();
	fireEvent.click(await screen.findByRole("button", { name: "Show details for job job-1" }));
	const heading = await screen.findByRole("heading", { name: "Batch 2" });
	const batch = within(heading.closest("section")!);
	fireEvent.click(batch.getByRole("button", { name: "Start" }));
	fireEvent.click(batch.getByRole("button", { name: "Start" }));
	expect(batch.getByRole("button", { name: "Start" })).toBeDisabled();
	expect(posts).toEqual(["/api/translation-jobs/job-1/batches/batch-1/start"]);
	release();
	await within(screen.getByRole("dialog")).findByText(/tasks could not be queued/);
	await waitFor(() => expect(batch.getByRole("button", { name: "Resume" })).toBeEnabled());
});
it("retains the previous snapshot and shows a refresh error", async () => {
	const { failReads } = setup();
	await screen.findByRole("heading", { name: "Job job-1" });
	failReads();
	fireEvent.click(screen.getByRole("button", { name: "Refresh jobs" }));
	await screen.findByRole("alert");
	expect(screen.getByRole("alert")).toHaveTextContent("Read unavailable");
	expect(screen.getByRole("heading", { name: "Job job-1" })).toBeInTheDocument();
});

it("polls the current page and stops polling when the viewer unmounts", async () => {
	vi.useFakeTimers();
	const harness = await act(async () => setup());
	expect(harness.reads).toHaveLength(1);
	await act(async () => {
		await vi.advanceTimersByTimeAsync(5000);
	});
	expect(harness.reads).toHaveLength(2);
	harness.view.unmount();
	await act(async () => {
		await vi.advanceTimersByTimeAsync(10000);
	});
	expect(harness.reads).toHaveLength(2);
});
