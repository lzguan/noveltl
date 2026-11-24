import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
	createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost,
	readAutoLabelRunsAutoLabelRunsGet,
	readLabelPromotionsNovelsNovelIdLabelPromotionsGet,
} from "@/api/endpoints/default/default";
import { DoNothingParamsValue, type AutoLabelRun } from "@/api/models";
import { Prov } from "../../controller/types/helperTypes";
import { LGProvId } from "../../controller/types/idTypes";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";
import { AutoLabelPanel } from "./AutoLabelPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	createAutolabelsAutoLabelsPost: vi.fn(),
	createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost: vi.fn(),
	readAutoLabelRunsAutoLabelRunsGet: vi.fn(),
	readAutoLabelsByRunAutoLabelRunsRunIdAutoLabelsGet: vi.fn(),
	readLabelPromotionsNovelsNovelIdLabelPromotionsGet: vi.fn(),
}));

const readRuns = vi.mocked(readAutoLabelRunsAutoLabelRunsGet);
const readPromotions = vi.mocked(readLabelPromotionsNovelsNovelIdLabelPromotionsGet);
const createPromotion = vi.mocked(createLabelPromotionLabelGroupsLabelGroupIdLabelPromotionsPost);

const RUN_B: AutoLabelRun = {
	createdAt: "2026-01-01T00:00:00Z",
	modelName: "do_nothing",
	modelParams: DoNothingParamsValue,
	novelId: "novel-1",
	runId: "22222222-0000-0000-0000-000000000002",
	triggeredBy: "user-1",
};

const NAMES_ID = LGProvId("00000000-0000-0000-0000-000000000005");
const PLACES_ID = LGProvId("00000000-0000-0000-0000-000000000006");

function labelGroup(labelGroupName: string): LabelGroupView {
	return { labelGroup: Prov({ labelGroupName }), color: 0, visible: true, status: "ready" };
}

const LABEL_GROUPS: [LGProvId, LabelGroupView][] = [
	[NAMES_ID, labelGroup("Names")],
	[PLACES_ID, labelGroup("Places")],
];

beforeEach(() => {
	readRuns.mockReset();
	readPromotions.mockReset();
	createPromotion.mockReset();
	readRuns.mockResolvedValue({ status: 200, data: [RUN_B], headers: new Headers() });
	readPromotions.mockResolvedValue({ status: 200, data: [], headers: new Headers() });
});

async function openPromoteDialog() {
	const menu = await screen.findByRole("button", { name: "More actions for Run 22222222" });
	fireEvent.keyDown(menu, { key: "Enter" });
	fireEvent.click(await screen.findByRole("menuitem", { name: "Promote…" }));
	return within(await screen.findByRole("dialog"));
}

describe("AutoLabelPanel", () => {
	it("promotes a run from its actions menu into the chosen label group", async () => {
		const setActive = vi.fn();
		createPromotion.mockResolvedValueOnce({
			status: 202,
			data: { promotionId: "promo-1", itemCount: 2 },
			headers: new Headers(),
		});

		render(
			<AutoLabelPanel
				novelId="novel-1"
				labelGroupServerId={(id) => (id === NAMES_ID ? "lg-names" : "lg-places")}
				onLabelGroupPromoted={vi.fn()}
				chapterNumByServerId={new Map()}
				currentChapterId={null}
				openChapterContentIds={new Map()}
				labelGroups={LABEL_GROUPS}
				activeId={NAMES_ID}
				setActive={setActive}
				previewEnabled={false}
				previewLoading={false}
				onSetPreviewEnabled={vi.fn()}
				onSelectedRunChange={vi.fn()}
			/>,
		);

		const dialog = await openPromoteDialog();
		expect(dialog.getByRole("combobox", { name: "Label group" })).toHaveTextContent("Names");
		expect(
			dialog.getByRole("switch", { name: "Skip chapters with existing labels" }),
		).toBeChecked();
		fireEvent.change(dialog.getByLabelText("Start chapter"), { target: { value: "2" } });
		fireEvent.click(dialog.getByRole("button", { name: "Promote" }));

		await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
		expect(createPromotion).toHaveBeenCalledWith("lg-names", {
			runId: RUN_B.runId,
			start: 2,
			end: null,
			skipExistingLabels: true,
		});
		expect(setActive).toHaveBeenCalledWith(NAMES_ID);
	});

	it("allows opting into promoting into chapters that already have labels", async () => {
		createPromotion.mockResolvedValueOnce({
			status: 202,
			data: { promotionId: "promo-2", itemCount: 3 },
			headers: new Headers(),
		});

		render(
			<AutoLabelPanel
				novelId="novel-1"
				labelGroupServerId={() => "lg-names"}
				onLabelGroupPromoted={vi.fn()}
				chapterNumByServerId={new Map()}
				currentChapterId={null}
				openChapterContentIds={new Map()}
				labelGroups={LABEL_GROUPS}
				activeId={NAMES_ID}
				setActive={vi.fn()}
				previewEnabled={false}
				previewLoading={false}
				onSetPreviewEnabled={vi.fn()}
				onSelectedRunChange={vi.fn()}
			/>,
		);

		const dialog = await openPromoteDialog();
		fireEvent.click(dialog.getByRole("switch", { name: "Skip chapters with existing labels" }));
		fireEvent.click(dialog.getByRole("button", { name: "Promote" }));

		await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
		expect(createPromotion).toHaveBeenCalledWith("lg-names", {
			runId: RUN_B.runId,
			start: null,
			end: null,
			skipExistingLabels: false,
		});
	});

	it("keeps the dialog open and shows an error when a promotion cannot start", async () => {
		const setActive = vi.fn();
		createPromotion.mockResolvedValueOnce({
			status: 409,
			data: { detail: "Already running" },
			headers: new Headers(),
		});

		render(
			<AutoLabelPanel
				novelId="novel-1"
				labelGroupServerId={() => "lg-names"}
				onLabelGroupPromoted={vi.fn()}
				chapterNumByServerId={new Map()}
				currentChapterId={null}
				openChapterContentIds={new Map()}
				labelGroups={LABEL_GROUPS}
				activeId={NAMES_ID}
				setActive={setActive}
				previewEnabled={false}
				previewLoading={false}
				onSetPreviewEnabled={vi.fn()}
				onSelectedRunChange={vi.fn()}
			/>,
		);

		const dialog = await openPromoteDialog();
		fireEvent.click(dialog.getByRole("button", { name: "Promote" }));

		expect(await dialog.findByRole("alert")).toHaveTextContent(
			"This run is already being promoted into that label group.",
		);
		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(setActive).not.toHaveBeenCalled();
	});
});
