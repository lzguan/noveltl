import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { DoNothingParamsValue } from "@/api/models";
import type { AutoLabelRunEntry } from "./autoLabelRunsState";
import { AutoLabelRunsList } from "./AutoLabelRunsList";

const RUN_A_ID = "11111111-0000-0000-0000-000000000001";
const RUN_B_ID = "22222222-0000-0000-0000-000000000002";

function makeEntry(runId: string, createdAt: string): AutoLabelRunEntry {
	return {
		run: {
			createdAt,
			modelName: "do_nothing",
			modelParams: DoNothingParamsValue,
			novelId: "00000000-0000-0000-0000-000000000003",
			runId,
			triggeredBy: "00000000-0000-0000-0000-000000000004",
		},
		status: "idle",
	};
}

const RUNS: readonly AutoLabelRunEntry[] = [
	makeEntry(RUN_A_ID, "2026-01-02T00:00:00Z"),
	makeEntry(RUN_B_ID, "2026-01-01T00:00:00Z"),
];

function Harness({
	onSelectRun,
	onDeselectRun,
	onReloadRun,
	onPromoteRun = () => undefined,
}: {
	onSelectRun: (runId: string) => void;
	onDeselectRun: () => void;
	onReloadRun: (runId: string) => void;
	onPromoteRun?: Parameters<typeof AutoLabelRunsList>[0]["onPromoteRun"];
}) {
	const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
	return (
		<AutoLabelRunsList
			runs={RUNS}
			selectedRunId={selectedRunId}
			refreshing={false}
			chapterNumById={new Map()}
			openChapterContentIds={new Map()}
			currentChapterId={null}
			onSelectRun={(runId) => {
				setSelectedRunId(runId);
				onSelectRun(runId);
			}}
			onDeselectRun={() => {
				setSelectedRunId(null);
				onDeselectRun();
			}}
			onRefreshAllRuns={() => undefined}
			onReloadRun={onReloadRun}
			canPromote
			onPromoteRun={onPromoteRun}
		/>
	);
}

describe("AutoLabelRunsList", () => {
	it("keeps selection, expansion, and reload as independent controls", async () => {
		const onSelectRun = vi.fn();
		const onDeselectRun = vi.fn();
		const onReloadRun = vi.fn();
		render(
			<Harness
				onSelectRun={onSelectRun}
				onDeselectRun={onDeselectRun}
				onReloadRun={onReloadRun}
			/>,
		);

		const runARow = await screen.findByRole("button", {
			name: /^Run 11111111/,
		});
		expect(
			screen.queryByText("Reload this run to load chapter statuses."),
		).not.toBeInTheDocument();

		fireEvent.click(runARow);

		expect(onSelectRun).toHaveBeenCalledWith(RUN_A_ID);
		expect(runARow).toHaveAttribute("aria-pressed", "true");
		expect(
			screen.queryByText("Reload this run to load chapter statuses."),
		).not.toBeInTheDocument();

		fireEvent.click(screen.getByRole("button", { name: "Expand Run 11111111" }));
		expect(screen.getAllByText("Reload this run to load chapter statuses.")).toHaveLength(1);
		expect(onSelectRun).toHaveBeenCalledTimes(1);

		fireEvent.click(screen.getByRole("button", { name: "Expand Run 22222222" }));
		expect(screen.getAllByText("Reload this run to load chapter statuses.")).toHaveLength(2);
		expect(runARow).toHaveAttribute("aria-pressed", "true");

		fireEvent.click(runARow);
		expect(onDeselectRun).toHaveBeenCalledOnce();
		expect(runARow).toHaveAttribute("aria-pressed", "false");
		expect(screen.getAllByText("Reload this run to load chapter statuses.")).toHaveLength(2);

		fireEvent.click(screen.getByRole("button", { name: "Reload Run 11111111" }));
		expect(onReloadRun).toHaveBeenCalledWith(RUN_A_ID);
		expect(onSelectRun).toHaveBeenCalledTimes(1);
		expect(onDeselectRun).toHaveBeenCalledOnce();
		expect(screen.getAllByText("Reload this run to load chapter statuses.")).toHaveLength(2);
	});

	it("invokes onPromoteRun from the run actions menu", async () => {
		const onPromoteRun = vi.fn();
		render(
			<Harness
				onSelectRun={vi.fn()}
				onDeselectRun={vi.fn()}
				onReloadRun={vi.fn()}
				onPromoteRun={onPromoteRun}
			/>,
		);

		const menu = await screen.findByRole("button", { name: "More actions for Run 22222222" });
		fireEvent.keyDown(menu, { key: "Enter" });
		fireEvent.click(await screen.findByRole("menuitem", { name: "Promote…" }));

		expect(onPromoteRun).toHaveBeenCalledWith(expect.objectContaining({ runId: RUN_B_ID }));
	});
});
