import type { ComponentProps } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { updateNovelNovelsNovelIdPatch } from "@/api/endpoints/default/default";
import { Visibility } from "@/api/models";
import { ToolbarPanel } from "./ToolbarPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	updateNovelNovelsNovelIdPatch: vi.fn(),
}));

const updateNovel = vi.mocked(updateNovelNovelsNovelIdPatch);

function renderToolbar(overrides: Partial<ComponentProps<typeof ToolbarPanel>> = {}) {
	return render(
		<ToolbarPanel
			novelId="novel-1"
			novelTitle="Test Novel"
			novelVisibility={Visibility.NUMBER_0}
			publicChapterCount={2}
			totalChapterCount={5}
			currentChapterNum={null}
			hasPreviousChapter={false}
			hasNextChapter={false}
			mode="view"
			loading={false}
			onPreviousChapter={vi.fn()}
			onNextChapter={vi.fn()}
			onSetMode={vi.fn()}
			onVisibilityUpdated={vi.fn()}
			{...overrides}
		/>,
	);
}

beforeEach(() => {
	updateNovel.mockReset();
});

describe("ToolbarPanel", () => {
	it("updates novel visibility via the dialog", async () => {
		const onVisibilityUpdated = vi.fn();
		updateNovel.mockResolvedValueOnce({
			status: 200,
			data: {
				novelId: "novel-1",
				novelTitle: "Test Novel",
				novelType: "original",
				novelVisibility: Visibility.NUMBER_3,
				languageCode: "en",
				sourceWorkId: "sw-1",
			},
			headers: new Headers(),
		});

		renderToolbar({ onVisibilityUpdated });

		fireEvent.click(screen.getByRole("button", { name: "Novel visibility: Private" }));
		const dialog = within(await screen.findByRole("dialog"));
		expect(dialog.getByText("Currently 2 of 5 chapters are public.")).toBeVisible();
		expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();

		fireEvent.click(dialog.getByRole("radio", { name: /Public/ }));
		fireEvent.click(dialog.getByRole("button", { name: "Save" }));

		await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
		expect(updateNovel).toHaveBeenCalledWith("novel-1", {
			novelVisibility: Visibility.NUMBER_3,
		});
		expect(onVisibilityUpdated).toHaveBeenCalledWith(Visibility.NUMBER_3);
	});

	it("keeps the dialog open and shows an error when updating visibility fails", async () => {
		const onVisibilityUpdated = vi.fn();
		updateNovel.mockResolvedValueOnce({
			status: 422,
			data: {
				detail: [
					{
						loc: ["body", "novelVisibility"],
						msg: "Invalid visibility.",
						type: "value_error",
					},
				],
			},
			headers: new Headers(),
		});

		renderToolbar({
			publicChapterCount: 0,
			totalChapterCount: 3,
			onVisibilityUpdated,
		});

		fireEvent.click(screen.getByRole("button", { name: "Novel visibility: Private" }));
		const dialog = within(await screen.findByRole("dialog"));
		fireEvent.click(dialog.getByRole("radio", { name: /Unlisted/ }));
		fireEvent.click(dialog.getByRole("button", { name: "Save" }));

		expect(await dialog.findByRole("alert")).toHaveTextContent(
			"body.novelVisibility: Invalid visibility.",
		);
		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(onVisibilityUpdated).not.toHaveBeenCalled();
	});

	it("disables chapter navigation and shows a placeholder when no chapter is open", () => {
		const onPreviousChapter = vi.fn();
		const onNextChapter = vi.fn();

		renderToolbar({
			currentChapterNum: null,
			hasPreviousChapter: true,
			hasNextChapter: true,
			onPreviousChapter,
			onNextChapter,
		});

		const nav = within(screen.getByRole("group", { name: "Chapter navigation" }));
		const prevButton = nav.getByRole("button", { name: "Previous chapter" });
		const nextButton = nav.getByRole("button", { name: "Next chapter" });

		expect(nav.getByText("—")).toBeVisible();
		expect(prevButton).toBeDisabled();
		expect(nextButton).toBeDisabled();

		fireEvent.click(prevButton);
		fireEvent.click(nextButton);
		expect(onPreviousChapter).not.toHaveBeenCalled();
		expect(onNextChapter).not.toHaveBeenCalled();
	});

	it("shows the current chapter number and navigates to previous and next chapters", () => {
		const onPreviousChapter = vi.fn();
		const onNextChapter = vi.fn();

		renderToolbar({
			currentChapterNum: 2,
			hasPreviousChapter: true,
			hasNextChapter: true,
			onPreviousChapter,
			onNextChapter,
		});

		const nav = within(screen.getByRole("group", { name: "Chapter navigation" }));
		const prevButton = nav.getByRole("button", { name: "Previous chapter" });
		const nextButton = nav.getByRole("button", { name: "Next chapter" });

		expect(nav.getByText("Ch. 2")).toBeVisible();
		expect(prevButton).toBeEnabled();
		expect(nextButton).toBeEnabled();

		fireEvent.click(prevButton);
		fireEvent.click(nextButton);
		expect(onPreviousChapter).toHaveBeenCalledTimes(1);
		expect(onNextChapter).toHaveBeenCalledTimes(1);
	});

	it("disables previous on the first chapter and next on the last chapter", () => {
		const { rerender } = renderToolbar({
			currentChapterNum: 0,
			hasPreviousChapter: false,
			hasNextChapter: true,
		});

		const nav = within(screen.getByRole("group", { name: "Chapter navigation" }));
		expect(nav.getByText("Ch. 0")).toBeVisible();
		expect(nav.getByRole("button", { name: "Previous chapter" })).toBeDisabled();
		expect(nav.getByRole("button", { name: "Next chapter" })).toBeEnabled();

		rerender(
			<ToolbarPanel
				novelId="novel-1"
				novelTitle="Test Novel"
				novelVisibility={Visibility.NUMBER_0}
				publicChapterCount={2}
				totalChapterCount={5}
				currentChapterNum={5}
				hasPreviousChapter={true}
				hasNextChapter={false}
				mode="view"
				loading={false}
				onPreviousChapter={vi.fn()}
				onNextChapter={vi.fn()}
				onSetMode={vi.fn()}
				onVisibilityUpdated={vi.fn()}
			/>,
		);

		expect(nav.getByText("Ch. 5")).toBeVisible();
		expect(nav.getByRole("button", { name: "Previous chapter" })).toBeEnabled();
		expect(nav.getByRole("button", { name: "Next chapter" })).toBeDisabled();
	});
});
