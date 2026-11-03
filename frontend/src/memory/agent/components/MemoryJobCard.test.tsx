import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";

import {
	readMemoryTasksMemoryAgentJobsMemoryJobIdTasksGet,
	retryMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdRetryPost,
} from "@/api/endpoints/default/default";
import type { MemoryChapterTask, MemoryJobSummary } from "@/api/models";
import { MemoryJobCard } from "./MemoryJobCard";

// Replace the HTTP boundary; keep the card, task rows, and loading hook real.
vi.mock("@/api/endpoints/default/default", async (importOriginal) => {
	const original = await importOriginal<typeof import("@/api/endpoints/default/default")>();
	return {
		...original,
		readMemoryTasksMemoryAgentJobsMemoryJobIdTasksGet: vi.fn(),
		retryMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdRetryPost: vi.fn(),
	};
});

const recording: MemoryChapterTask = {
	memoryJobId: "job-1",
	chapterId: "chapter-1",
	chapterNum: 1,
	stageNum: 0,
	taskStatus: "completed",
	attemptCount: 1,
	createdAt: "2026-11-01T00:00:00Z",
	updatedAt: "2026-11-01T00:00:00Z",
};
const naming: MemoryChapterTask = {
	...recording,
	stageNum: 1,
	taskStatus: "failed",
};
const summary: MemoryJobSummary = {
	job: {
		memoryJobId: "job-1",
		memoryGroupId: "group-1",
		claimExpiresAt: null,
		createdAt: recording.createdAt,
		updatedAt: recording.updatedAt,
		jobParams: {
			version: 2,
			recordMemories: { modelName: "deepseek:deepseek-v4-flash-low", toolsets: {} },
			translateTerms: { modelName: "deepseek:deepseek-v4-flash-low" },
		},
	},
	taskCounts: { completed: 1, pending: 0, processing: 0, failed: 1 },
	isClaimed: false,
};

function Harness() {
	const [expanded, setExpanded] = useState(false);
	return (
		<MemoryJobCard
			summary={summary}
			claimed={false}
			expanded={expanded}
			watchingDispatch={false}
			refreshingSummary={false}
			onExpandedChange={setExpanded}
			onReloadSummary={async () => true}
			onRemoveJob={() => {}}
			onWatchDispatch={() => {}}
		/>
	);
}

it("retries the naming stage while showing recording as completed", async () => {
	vi.mocked(readMemoryTasksMemoryAgentJobsMemoryJobIdTasksGet).mockResolvedValue({
		data: { count: 2, rows: [recording, naming] },
		status: 200,
		headers: new Headers(),
	});
	vi.mocked(retryMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdRetryPost).mockResolvedValue({
		data: { ...naming, taskStatus: "pending" },
		status: 202,
		headers: new Headers(),
	});
	render(<Harness />);
	fireEvent.click(screen.getByRole("button", { name: /Memory agent/ }));
	expect(await screen.findByText(/Chapter 1 · Record memories/)).toBeVisible();
	expect(screen.getByText(/Chapter 1 · Translate terms/)).toBeVisible();
	expect(screen.getByText("Done")).toBeVisible();
	fireEvent.click(screen.getByRole("button", { name: "Retry" }));
	await waitFor(() =>
		expect(
			retryMemoryTaskMemoryAgentJobsMemoryJobIdTasksChapterIdRetryPost,
		).toHaveBeenCalledWith("job-1", "chapter-1", { stageNum: 1 }),
	);
});
