import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
	PublishJobStatus,
	PublishMode,
	TargetRole,
	type NovelPublishStatus,
	type PublishJobRead,
	type PublishingTargetRead,
} from "@/api/models";
import { AppRoutes } from "@/routes";
import { PublishNovelDialog } from "./PublishNovelDialog";

function jsonResponse(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { "Content-Type": "application/json" },
	});
}

function requestUrl(input: RequestInfo | URL): string {
	if (typeof input === "string") return input;
	if (input instanceof URL) return input.toString();
	return input.url;
}

const target: PublishingTargetRead = {
	targetId: "target-1",
	name: "Production Reader",
	apiBaseUrl: "https://reader.example.com/api",
	publicBaseUrl: "https://reader.example.com",
	keyPrefix: "ntr_live",
	role: TargetRole.owner,
	createdByUserId: "user-1",
	createdAt: "2026-11-01T00:00:00Z",
	updatedAt: "2026-11-01T00:00:00Z",
};

const initialStatus: NovelPublishStatus = {
	existsOnReader: true,
	readerNovelId: "reader-novel-1",
	publicUrl: "https://reader.example.com/novels/reader-novel-1",
	studioChapterCount: 10,
	readerChapterCount: 8,
	newCount: 3,
	outdatedCount: 2,
	upToDateCount: 5,
	readerOnlyCount: 1,
	activeJob: null,
	latestJob: null,
};

const syncedStatus: NovelPublishStatus = {
	...initialStatus,
	readerChapterCount: 11,
	newCount: 0,
	outdatedCount: 0,
	upToDateCount: 10,
	readerOnlyCount: 1,
};

function makeJob(overrides: Partial<PublishJobRead> = {}): PublishJobRead {
	return {
		jobId: "job-1",
		novelId: "novel-1",
		targetId: "target-1",
		initiatedByUserId: "user-1",
		mode: PublishMode.outdated,
		startChapter: null,
		endChapter: null,
		includeNovelMetadata: true,
		status: PublishJobStatus.pending,
		totalChapters: 5,
		syncedChapters: 0,
		cursorChapterNum: null,
		readerNovelId: "reader-novel-1",
		publicUrl: "https://reader.example.com/novels/reader-novel-1",
		errorMessage: null,
		createdAt: "2026-11-05T00:00:00Z",
		updatedAt: "2026-11-05T00:00:00Z",
		completedAt: null,
		...overrides,
	};
}

function renderDialog(onClose = vi.fn()) {
	return render(
		<MemoryRouter>
			<PublishNovelDialog novelId="novel-1" novelTitle="Test Novel" onClose={onClose} />
		</MemoryRouter>,
	);
}

describe("PublishNovelDialog", () => {
	let fetchSpy: ReturnType<typeof vi.fn<typeof fetch>>;

	beforeEach(() => {
		fetchSpy = vi.fn<typeof fetch>();
		vi.stubGlobal("fetch", fetchSpy);
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.unstubAllGlobals();
	});

	it("prompts the user to configure a target in Settings when none exist", async () => {
		fetchSpy.mockResolvedValue(jsonResponse(200, []));

		renderDialog();

		const link = await screen.findByRole("link", {
			name: "Configure a Reader target in Settings",
		});
		expect(link).toBeVisible();
		expect(link).toHaveAttribute("href", AppRoutes.SETTINGS);
	});

	it("renders live diff counts, Reader link, and reader-only notice", async () => {
		fetchSpy.mockImplementation(async (input) => {
			const url = requestUrl(input);
			if (url === "/api/publishing/targets") return jsonResponse(200, [target]);
			if (url === "/api/novels/novel-1/publish/status?targetId=target-1") {
				return jsonResponse(200, initialStatus);
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderDialog();

		const dialog = within(await screen.findByRole("dialog", { name: "Publish novel" }));
		expect(await dialog.findByText("New: 3")).toBeVisible();
		expect(dialog.getByText("Outdated: 2")).toBeVisible();
		expect(dialog.getByText("Up to date: 5")).toBeVisible();
		expect(
			dialog.getByText(
				"1 chapter(s) exist on Reader but not in Studio; remove via Reader Admin",
			),
		).toBeVisible();

		const readerLink = dialog.getByRole("link", { name: "View on Reader ↗" });
		expect(readerLink).toHaveAttribute(
			"href",
			"https://reader.example.com/novels/reader-novel-1",
		);
		expect(readerLink).toHaveAttribute("target", "_blank");
		expect(readerLink).toHaveAttribute("rel", "noopener noreferrer");
	});

	it("validates chapter range inputs client-side and sends range bounds when valid", async () => {
		let capturedBody: string | null = null;
		fetchSpy.mockImplementation(async (input, init) => {
			const url = requestUrl(input);
			if (url === "/api/publishing/targets") return jsonResponse(200, [target]);
			if (url === "/api/novels/novel-1/publish/status?targetId=target-1") {
				return jsonResponse(200, initialStatus);
			}
			if (url === "/api/novels/novel-1/publish" && init?.method === "POST") {
				capturedBody = typeof init.body === "string" ? init.body : null;
				return jsonResponse(
					202,
					makeJob({
						mode: PublishMode.range,
						startChapter: 1,
						endChapter: 5,
						status: PublishJobStatus.completed,
						syncedChapters: 5,
					}),
				);
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderDialog();

		const dialog = within(await screen.findByRole("dialog", { name: "Publish novel" }));
		await dialog.findByText("New: 3");

		fireEvent.click(dialog.getByRole("radio", { name: /Chapter range/ }));
		const startButton = dialog.getByRole("button", { name: "Start publish" });
		expect(startButton).toBeDisabled();

		fireEvent.change(dialog.getByLabelText("Start chapter"), { target: { value: "8" } });
		fireEvent.change(dialog.getByLabelText("End chapter"), { target: { value: "3" } });
		expect(dialog.getByRole("alert")).toHaveTextContent(
			"Start chapter must be less than or equal to end chapter.",
		);
		expect(startButton).toBeDisabled();

		fireEvent.change(dialog.getByLabelText("Start chapter"), { target: { value: "-1" } });
		expect(dialog.getByRole("alert")).toHaveTextContent(
			"Chapter numbers must be whole integers greater than or equal to 0.",
		);
		expect(startButton).toBeDisabled();

		fireEvent.change(dialog.getByLabelText("Start chapter"), { target: { value: "1" } });
		fireEvent.change(dialog.getByLabelText("End chapter"), { target: { value: "5" } });
		expect(startButton).toBeEnabled();

		fireEvent.click(startButton);
		await waitFor(() => expect(capturedBody).not.toBeNull());
		expect(JSON.parse(capturedBody ?? "{}")).toEqual({
			targetId: "target-1",
			mode: PublishMode.range,
			includeNovelMetadata: true,
			startChapter: 1,
			endChapter: 5,
		});
	});

	it("starts a job, polls until completed, and refreshes status", async () => {
		vi.useFakeTimers();
		let statusCalls = 0;
		let pollCalls = 0;

		fetchSpy.mockImplementation(async (input, init) => {
			const url = requestUrl(input);
			if (url === "/api/publishing/targets") return jsonResponse(200, [target]);
			if (url === "/api/novels/novel-1/publish/status?targetId=target-1") {
				statusCalls += 1;
				return jsonResponse(200, statusCalls === 1 ? initialStatus : syncedStatus);
			}
			if (url === "/api/novels/novel-1/publish" && init?.method === "POST") {
				return jsonResponse(202, makeJob({ status: PublishJobStatus.pending }));
			}
			if (url === "/api/novels/novel-1/publish/jobs/job-1") {
				pollCalls += 1;
				if (pollCalls === 1) {
					return jsonResponse(
						200,
						makeJob({
							status: PublishJobStatus.processing,
							syncedChapters: 3,
							totalChapters: 5,
						}),
					);
				}
				return jsonResponse(
					200,
					makeJob({
						status: PublishJobStatus.completed,
						syncedChapters: 5,
						totalChapters: 5,
						completedAt: "2026-11-05T00:01:00Z",
					}),
				);
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderDialog();

		await act(async () => {
			await vi.advanceTimersByTimeAsync(0);
		});

		const dialog = within(screen.getByRole("dialog", { name: "Publish novel" }));
		expect(dialog.getByText("New: 3")).toBeVisible();

		fireEvent.click(dialog.getByRole("button", { name: "Start publish" }));
		await act(async () => {
			await vi.advanceTimersByTimeAsync(0);
		});

		expect(dialog.getByText("Pending")).toBeVisible();
		expect(dialog.getByText("0 / 5 chapters")).toBeVisible();
		expect(dialog.getByRole("button", { name: "Publishing..." })).toBeDisabled();

		await act(async () => {
			await vi.advanceTimersByTimeAsync(1500);
		});
		expect(dialog.getByText("Processing")).toBeVisible();
		expect(dialog.getByText("3 / 5 chapters")).toBeVisible();

		await act(async () => {
			await vi.advanceTimersByTimeAsync(1500);
		});
		expect(dialog.getByText("Completed")).toBeVisible();
		expect(dialog.getByText("5 / 5 chapters")).toBeVisible();
		expect(dialog.getByText("New: 0")).toBeVisible();
		expect(dialog.getByText("Up to date: 10")).toBeVisible();
		expect(dialog.getByRole("button", { name: "Start publish" })).toBeEnabled();
		expect(statusCalls).toBe(2);
	});

	it("shows the failure message and a Retry button when a job fails", async () => {
		vi.useFakeTimers();

		fetchSpy.mockImplementation(async (input, init) => {
			const url = requestUrl(input);
			if (url === "/api/publishing/targets") return jsonResponse(200, [target]);
			if (url === "/api/novels/novel-1/publish/status?targetId=target-1") {
				return jsonResponse(200, initialStatus);
			}
			if (url === "/api/novels/novel-1/publish" && init?.method === "POST") {
				return jsonResponse(202, makeJob({ status: PublishJobStatus.processing }));
			}
			if (url === "/api/novels/novel-1/publish/jobs/job-1") {
				return jsonResponse(
					200,
					makeJob({
						status: PublishJobStatus.failed,
						syncedChapters: 2,
						totalChapters: 5,
						errorMessage: "Reader returned 502 Bad Gateway",
					}),
				);
			}
			return jsonResponse(404, { detail: "Not found" });
		});

		renderDialog();

		await act(async () => {
			await vi.advanceTimersByTimeAsync(0);
		});

		const dialog = within(screen.getByRole("dialog", { name: "Publish novel" }));
		fireEvent.click(dialog.getByRole("button", { name: "Start publish" }));
		await act(async () => {
			await vi.advanceTimersByTimeAsync(0);
		});

		await act(async () => {
			await vi.advanceTimersByTimeAsync(1500);
		});

		expect(dialog.getByText("Failed")).toBeVisible();
		expect(dialog.getByRole("alert")).toHaveTextContent("Reader returned 502 Bad Gateway");
		expect(dialog.getByRole("button", { name: "Retry" })).toBeEnabled();
	});
});
