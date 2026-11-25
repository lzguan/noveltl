import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { updateNovelNovelsNovelIdPatch } from "@/api/endpoints/default/default";
import { Visibility } from "@/api/models";
import { ToolbarPanel } from "./ToolbarPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	updateNovelNovelsNovelIdPatch: vi.fn(),
}));

const updateNovel = vi.mocked(updateNovelNovelsNovelIdPatch);

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

		render(
			<ToolbarPanel
				novelId="novel-1"
				novelTitle="Test Novel"
				novelVisibility={Visibility.NUMBER_0}
				publicChapterCount={2}
				totalChapterCount={5}
				mode="view"
				loading={false}
				onSetMode={vi.fn()}
				onVisibilityUpdated={onVisibilityUpdated}
			/>,
		);

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

		render(
			<ToolbarPanel
				novelId="novel-1"
				novelTitle="Test Novel"
				novelVisibility={Visibility.NUMBER_0}
				publicChapterCount={0}
				totalChapterCount={3}
				mode="view"
				loading={false}
				onSetMode={vi.fn()}
				onVisibilityUpdated={onVisibilityUpdated}
			/>,
		);

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
});
