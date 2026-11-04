import {
	editMemoryContentMemoriesMemoryIdContentPatch,
	editMemoryExpirationMemoriesMemoryIdExpirationPatch,
	editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch,
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet,
	removeMemoryMemoriesMemoryIdDelete,
} from "@/api/endpoints/default/default";
import type { Memory } from "@/api/models";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryBrowser } from "./MemoryBrowser";

// Replace HTTP only; keep the browser, its hook, rows, and dialogs real.
vi.mock("@/api/endpoints/default/default", () => ({
	editMemoryContentMemoriesMemoryIdContentPatch: vi.fn(),
	editMemoryExpirationMemoriesMemoryIdExpirationPatch: vi.fn(),
	editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch: vi.fn(),
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet: vi.fn(),
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet: vi.fn(),
	removeMemoryMemoriesMemoryIdDelete: vi.fn(),
}));

beforeAll(() => {
	class ResizeObserverMock implements ResizeObserver {
		disconnect() {}
		observe() {}
		unobserve() {}
	}
	vi.stubGlobal("ResizeObserver", ResizeObserverMock);
	Object.defineProperties(HTMLElement.prototype, {
		hasPointerCapture: { configurable: true, value: () => false },
		releasePointerCapture: { configurable: true, value: () => undefined },
		scrollIntoView: { configurable: true, value: () => undefined },
		setPointerCapture: { configurable: true, value: () => undefined },
	});
});

const memory: Memory = {
	creatorType: "agent",
	memoryContent: "Lin Fan is the sect's newest inner disciple.",
	memoryEndNum: null,
	memoryId: "memory-1",
	mark: "ability",
	memoryReviewStatus: "pending",
	memoryStartNum: 12,
	memoryType: "fact",
	pluginName: "glossary",
	supersedesMemoryId: null,
};

function openMenu(label: string) {
	const trigger = screen.getByRole("button", { name: label });
	fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: "mouse" });
}

function renderBrowser(chapterId: string | null = "chapter-12", chapterNum: number | null = 12) {
	return render(
		<MemoryBrowser memoryGroupId="group-1" chapterId={chapterId} chapterNum={chapterNum} />,
	);
}

describe("MemoryBrowser", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(
			readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
		).mockResolvedValue({
			status: 200,
			data: { count: 1, rows: [memory] },
			headers: new Headers(),
		});
		vi.mocked(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).mockResolvedValue({
			status: 200,
			data: { count: 1, rows: [memory] },
			headers: new Headers(),
		});
	});

	it("edits memory content and reloads the visible memory query", async () => {
		vi.mocked(editMemoryContentMemoriesMemoryIdContentPatch).mockResolvedValueOnce({
			status: 200,
			data: { ...memory, memoryContent: "Updated memory" },
			headers: new Headers(),
		});
		renderBrowser();
		await screen.findByText(memory.memoryContent);

		openMenu("Memory actions");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Edit memory" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Content" }), {
			target: { value: "  Updated memory  " },
		});
		expect(screen.getByRole("textbox", { name: "Mark (optional)" })).toHaveValue("ability");
		fireEvent.change(screen.getByRole("textbox", { name: "Mark (optional)" }), {
			target: { value: "  limitation  " },
		});
		fireEvent.click(screen.getByRole("button", { name: "Save memory" }));

		await waitFor(() =>
			expect(editMemoryContentMemoriesMemoryIdContentPatch).toHaveBeenCalledWith("memory-1", {
				memoryContent: "Updated memory",
				mark: "limitation",
			}),
		);
		await waitFor(() =>
			expect(
				readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
			).toHaveBeenCalledTimes(2),
		);
	});

	it("changes a memory review status from its action menu", async () => {
		vi.mocked(editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch).mockResolvedValueOnce({
			status: 200,
			data: { ...memory, memoryReviewStatus: "approved" },
			headers: new Headers(),
		});
		renderBrowser();
		await screen.findByText(memory.memoryContent);

		openMenu("Memory actions");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Review status" }));
		fireEvent.click(await screen.findByRole("menuitemradio", { name: "Approved" }));

		await waitFor(() =>
			expect(editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch).toHaveBeenCalledWith(
				"memory-1",
				{ reviewStatus: "approved" },
			),
		);
	});

	it("confirms memory deletion before reloading the visible query", async () => {
		vi.mocked(removeMemoryMemoriesMemoryIdDelete).mockResolvedValueOnce({
			status: 204,
			data: undefined,
			headers: new Headers(),
		});
		renderBrowser();
		await screen.findByText(memory.memoryContent);

		openMenu("Memory actions");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
		expect(removeMemoryMemoriesMemoryIdDelete).not.toHaveBeenCalled();
		fireEvent.click(screen.getByRole("button", { name: "Delete memory" }));

		await waitFor(() =>
			expect(removeMemoryMemoriesMemoryIdDelete).toHaveBeenCalledWith("memory-1"),
		);
		await waitFor(() =>
			expect(
				readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
			).toHaveBeenCalledTimes(2),
		);
	});

	it("expires a memory at the currently open chapter", async () => {
		vi.mocked(editMemoryExpirationMemoriesMemoryIdExpirationPatch).mockResolvedValueOnce({
			status: 200,
			data: { ...memory, memoryEndNum: 13 },
			headers: new Headers(),
		});
		renderBrowser("chapter-13", 13);
		await screen.findByText(memory.memoryContent);

		openMenu("Memory actions");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Expire at current chapter" }));
		fireEvent.click(screen.getByRole("button", { name: "Expire memory" }));

		await waitFor(() =>
			expect(editMemoryExpirationMemoriesMemoryIdExpirationPatch).toHaveBeenCalledWith(
				"memory-1",
				{ chapterId: "chapter-13" },
			),
		);
	});

	it("disables memory expiration when no chapter is open", async () => {
		renderBrowser(null, null);
		fireEvent.click(await screen.findByRole("checkbox", { name: "From all chapters" }));
		await screen.findByText(memory.memoryContent);

		openMenu("Memory actions");
		expect(
			await screen.findByRole("menuitem", { name: "Expire at current chapter" }),
		).toHaveAttribute("data-disabled");
	});
});
