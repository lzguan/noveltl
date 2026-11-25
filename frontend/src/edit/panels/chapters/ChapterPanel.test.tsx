import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { actionUpdateChaptersVisibilityNovelsNovelIdChaptersVisibilityPost } from "@/api/endpoints/default/default";
import { Prov } from "../../controller/types/helperTypes";
import { CProvId, type ProvChapter } from "../../controller/types/idTypes";
import { ChapterPanel } from "./ChapterPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	actionUpdateChaptersVisibilityNovelsNovelIdChaptersVisibilityPost: vi.fn(),
}));

const updateVisibility = vi.mocked(
	actionUpdateChaptersVisibilityNovelsNovelIdChaptersVisibilityPost,
);

function makeChapter(chapterNum: number, chapterIsPublic: boolean): ProvChapter {
	return Prov({
		chapterId: CProvId(`chapter-${chapterNum}`),
		chapterNum,
		chapterTitle: `Chapter ${chapterNum}`,
		chapterIsPublic,
		novelId: "novel-1",
	});
}

const CHAPTERS = [makeChapter(1, true), makeChapter(2, false), makeChapter(3, false)];

beforeEach(() => {
	updateVisibility.mockReset();
});

describe("ChapterPanel", () => {
	it("shows display-only icons by default and toggles per-chapter visibility in edit mode", async () => {
		const onSwitch = vi.fn();
		const onUpdated = vi.fn();
		updateVisibility.mockResolvedValueOnce({
			status: 200,
			data: { updatedChapterNums: [2], isPublic: true },
			headers: new Headers(),
		});

		render(
			<ChapterPanel
				novelId="novel-1"
				chapters={CHAPTERS}
				currentChapterId={null}
				onSwitchChapter={onSwitch}
				onAddChapter={vi.fn()}
				onChaptersVisibilityUpdated={onUpdated}
			/>,
		);

		expect(screen.getAllByLabelText("Public")).toHaveLength(1);
		expect(screen.getAllByLabelText("Private")).toHaveLength(2);
		expect(
			screen.queryByRole("button", { name: "Make chapter 2 public" }),
		).not.toBeInTheDocument();

		fireEvent.click(screen.getByRole("button", { name: "Manage chapter visibility" }));
		fireEvent.click(screen.getByRole("button", { name: "Make chapter 2 public" }));

		await waitFor(() => expect(onUpdated).toHaveBeenCalledWith([2], true));
		expect(updateVisibility).toHaveBeenCalledWith("novel-1", {
			start: 2,
			end: 2,
			isPublic: true,
		});
		expect(onSwitch).not.toHaveBeenCalled();

		fireEvent.click(screen.getByRole("button", { name: "Done" }));
		expect(
			screen.queryByRole("button", { name: "Make chapter 2 public" }),
		).not.toBeInTheDocument();
	});

	it("opens bulk visibility dialog from edit mode and updates a range", async () => {
		const onUpdated = vi.fn();
		updateVisibility.mockResolvedValueOnce({
			status: 200,
			data: { updatedChapterNums: [2, 3], isPublic: true },
			headers: new Headers(),
		});

		render(
			<ChapterPanel
				novelId="novel-1"
				chapters={CHAPTERS}
				currentChapterId={null}
				onSwitchChapter={vi.fn()}
				onAddChapter={vi.fn()}
				onChaptersVisibilityUpdated={onUpdated}
			/>,
		);

		fireEvent.click(screen.getByRole("button", { name: "Manage chapter visibility" }));
		fireEvent.click(screen.getByRole("button", { name: "Bulk edit…" }));
		const dialog = within(await screen.findByRole("dialog"));
		expect(dialog.getByText("Matches 3 of 3 chapters (1 public, 2 private).")).toBeVisible();

		fireEvent.change(dialog.getByLabelText("From chapter"), { target: { value: "2" } });
		fireEvent.change(dialog.getByLabelText("To chapter"), { target: { value: "3" } });
		expect(dialog.getByText("Matches 2 of 3 chapters (0 public, 2 private).")).toBeVisible();

		fireEvent.click(dialog.getByRole("button", { name: "Make public" }));

		await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
		expect(updateVisibility).toHaveBeenCalledWith("novel-1", {
			start: 2,
			end: 3,
			isPublic: true,
		});
		expect(onUpdated).toHaveBeenCalledWith([2, 3], true);
	});

	it("validates inverted ranges and keeps the dialog open on API errors", async () => {
		const onUpdated = vi.fn();
		updateVisibility.mockResolvedValueOnce({
			status: 401,
			data: { detail: "Insufficient permissions to perform this action." },
			headers: new Headers(),
		});

		render(
			<ChapterPanel
				novelId="novel-1"
				chapters={CHAPTERS}
				currentChapterId={null}
				onSwitchChapter={vi.fn()}
				onAddChapter={vi.fn()}
				onChaptersVisibilityUpdated={onUpdated}
			/>,
		);

		fireEvent.click(screen.getByRole("button", { name: "Manage chapter visibility" }));
		fireEvent.click(screen.getByRole("button", { name: "Bulk edit…" }));
		const dialog = within(await screen.findByRole("dialog"));

		fireEvent.change(dialog.getByLabelText("From chapter"), { target: { value: "3" } });
		fireEvent.change(dialog.getByLabelText("To chapter"), { target: { value: "1" } });
		expect(dialog.getByRole("alert")).toHaveTextContent(
			"Start chapter must be less than or equal to end chapter.",
		);
		expect(dialog.getByRole("button", { name: "Make private" })).toBeDisabled();

		fireEvent.change(dialog.getByLabelText("From chapter"), { target: { value: "" } });
		fireEvent.change(dialog.getByLabelText("To chapter"), { target: { value: "" } });
		fireEvent.click(dialog.getByRole("button", { name: "Make private" }));

		expect(await dialog.findByRole("alert")).toHaveTextContent(
			"Insufficient permissions to perform this action.",
		);
		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(onUpdated).not.toHaveBeenCalled();
	});
});
