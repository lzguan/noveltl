import { fireEvent, render, screen, within } from "@testing-library/react";
import { useEffect } from "react";
import { DoNothingParamsValue } from "@/api/models";
import { Prov } from "../../controller/types/helperTypes";
import { ALRProvId, ALRServId, LGProvId } from "../../controller/types/idTypes";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";
import { type AutoLabelRunView, useAutoLabelState } from "../../hooks/useAutoLabelState";
import { AutoLabelRunsPanel } from "./AutoLabelRunsPanel";

const RUN_A_ID = ALRProvId("00000000-0000-0000-0000-000000000001");
const RUN_B_ID = ALRProvId("00000000-0000-0000-0000-000000000002");
const RUN_A_SERV_ID = ALRServId("11111111-0000-0000-0000-000000000001");
const RUN_B_SERV_ID = ALRServId("22222222-0000-0000-0000-000000000002");

function makeRun(
	runId: typeof RUN_A_ID,
	servId: typeof RUN_A_SERV_ID,
	createdAt: string,
): AutoLabelRunView {
	return {
		run: {
			...Prov({
				createdAt,
				modelName: "do_nothing",
				modelParams: DoNothingParamsValue,
				novelId: "00000000-0000-0000-0000-000000000003",
				runId,
				triggeredBy: "00000000-0000-0000-0000-000000000004",
			}),
			servId,
		},
		status: "idle",
	};
}

const RUN_A = makeRun(RUN_A_ID, RUN_A_SERV_ID, "2026-01-02T00:00:00Z");
const RUN_B = makeRun(RUN_B_ID, RUN_B_SERV_ID, "2026-01-01T00:00:00Z");
const NAMES_ID = LGProvId("00000000-0000-0000-0000-000000000005");
const PLACES_ID = LGProvId("00000000-0000-0000-0000-000000000006");
function labelGroup(labelGroupName: string): LabelGroupView {
	return { labelGroup: Prov({ labelGroupName }), color: 0, visible: true, status: "ready" };
}
const LABEL_GROUPS: [LGProvId, LabelGroupView][] = [
	[NAMES_ID, labelGroup("Names")],
	[PLACES_ID, labelGroup("Places")],
];

function Harness({
	onSelectRun,
	onDeselectRun,
	onReloadRun,
	setActive = () => undefined,
	onPromote = () => undefined,
}: {
	onSelectRun: (runId: typeof RUN_A_ID) => void;
	onDeselectRun: () => void;
	onReloadRun: (runId: typeof RUN_A_ID) => void;
	setActive?: (id: LGProvId | null) => void;
	onPromote?: Parameters<typeof AutoLabelRunsPanel>[0]["onPromote"];
}) {
	const autoLabels = useAutoLabelState();
	const { setRunsList } = autoLabels;

	useEffect(() => {
		setRunsList([RUN_A, RUN_B]);
	}, [setRunsList]);

	return (
		<AutoLabelRunsPanel
			autoLabels={autoLabels}
			chapters={[]}
			currentChapterId={null}
			onSelectRun={(runId) => {
				autoLabels.setSelected(runId);
				onSelectRun(runId);
			}}
			onDeselectRun={() => {
				autoLabels.setSelected(null);
				onDeselectRun();
			}}
			onRefreshAllRuns={() => undefined}
			onReloadRun={onReloadRun}
			labelGroups={LABEL_GROUPS}
			activeId={NAMES_ID}
			setActive={setActive}
			onPromote={onPromote}
		/>
	);
}

describe("AutoLabelRunsPanel", () => {
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

	it("promotes a run from its actions menu into the chosen label group", async () => {
		const setActive = vi.fn();
		const onPromote = vi.fn();
		render(
			<Harness
				onSelectRun={vi.fn()}
				onDeselectRun={vi.fn()}
				onReloadRun={vi.fn()}
				setActive={setActive}
				onPromote={onPromote}
			/>,
		);

		const menu = await screen.findByRole("button", { name: "More actions for Run 22222222" });
		fireEvent.keyDown(menu, { key: "Enter" });
		fireEvent.click(await screen.findByRole("menuitem", { name: "Promote…" }));

		const dialog = within(await screen.findByRole("dialog"));
		expect(dialog.getByRole("combobox", { name: "Label group" })).toHaveTextContent("Names");
		fireEvent.change(dialog.getByLabelText("Start chapter"), { target: { value: "2" } });
		fireEvent.click(dialog.getByRole("button", { name: "Promote" }));

		expect(setActive).toHaveBeenCalledWith(NAMES_ID);
		expect(onPromote).toHaveBeenCalledWith(RUN_B_ID, NAMES_ID, { start: 2, end: undefined });
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});
});
