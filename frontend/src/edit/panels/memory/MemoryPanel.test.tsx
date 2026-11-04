import {
	addMemoryGroupMemoryGroupsPost,
	editMemoryContentMemoriesMemoryIdContentPatch,
	editMemoryExpirationMemoriesMemoryIdExpirationPatch,
	editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch,
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
	readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet,
	readAllLanguagesLanguagesGet,
	readConventionsMemoryGroupsMemoryGroupIdConventionsGet,
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet,
	readMemoryGroupsMemoryGroupsGet,
	removeMemoryMemoriesMemoryIdDelete,
} from "@/api/endpoints/default/default";
import type { GlossaryMemory, GlossaryTermSummary, Memory, MemoryGroup } from "@/api/models";
import { MemoryGroupsProvider } from "@/memory/context/MemoryGroupsContext";
import {
	fireEvent,
	render as renderWithTestingLibrary,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryPanel } from "./MemoryPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	addMemoryGroupMemoryGroupsPost: vi.fn(),
	editMemoryContentMemoriesMemoryIdContentPatch: vi.fn(),
	editMemoryExpirationMemoriesMemoryIdExpirationPatch: vi.fn(),
	editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch: vi.fn(),
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet: vi.fn(),
	readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet: vi.fn(),
	putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut: vi.fn(),
	readAllLanguagesLanguagesGet: vi.fn(),
	readConventionsMemoryGroupsMemoryGroupIdConventionsGet: vi.fn(),
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet: vi.fn(),
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet: vi.fn(),
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet: vi.fn(),
	readMemoryGroupsMemoryGroupsGet: vi.fn(),
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

const group: MemoryGroup = {
	memoryGroupId: "group-1",
	memoryGroupName: "Main glossary",
	memoryLanguage: "en",
	novelId: "novel-1",
};

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

const term: GlossaryTermSummary = {
	associatedMemoryCount: 14,
	reviewStatus: "approved",
	term: "林凡",
	termId: "term-1",
	termKind: "person",
};

const glossaryMemory: GlossaryMemory = {
	memory,
	terms: [
		{ reviewStatus: "approved", term: "林凡", termId: "term-1", termKind: "person" },
		{ reviewStatus: "pending", term: "青阳镇", termId: "term-2", termKind: "place" },
	],
};

function selectOption(label: string, optionName: string) {
	const select = screen.getByRole("combobox", { name: label });
	fireEvent.pointerDown(select, { button: 0, ctrlKey: false, pointerType: "mouse" });
	fireEvent.click(screen.getByRole("option", { name: optionName }));
}

async function selectView(name: string) {
	fireEvent.mouseDown(await screen.findByRole("tab", { name }), { button: 0, ctrlKey: false });
}

function openMenu(label: string) {
	const trigger = screen.getByRole("button", { name: label });
	fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: "mouse" });
}

function render(element: ReactElement) {
	return renderWithTestingLibrary(
		<MemoryGroupsProvider novelId="novel-1">{element}</MemoryGroupsProvider>,
	);
}

describe("MemoryPanel", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).mockResolvedValue({
			status: 200,
			data: [],
			headers: new Headers(),
		});
		vi.mocked(readMemoryGroupsMemoryGroupsGet).mockResolvedValue({
			status: 200,
			data: [group],
			headers: new Headers(),
		});
		vi.mocked(readAllLanguagesLanguagesGet).mockResolvedValue({
			status: 200,
			data: [
				{ languageCode: "en", languageName: "English" },
				{ languageCode: "ja", languageName: "Japanese" },
			],
			headers: new Headers(),
		});
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
		vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).mockResolvedValue({
			status: 200,
			data: { count: 1, rows: [term] },
			headers: new Headers(),
		});
		vi.mocked(
			readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
		).mockResolvedValue({
			status: 200,
			data: { count: 1, rows: [glossaryMemory] },
			headers: new Headers(),
		});
	});

	it("browses memories through direct scope and type events", async () => {
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);

		await waitFor(() =>
			expect(
				readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
			).toHaveBeenCalledWith(
				"group-1",
				"chapter-12",
				{ skip: 0, limit: 20, memoryTypes: undefined },
				expect.objectContaining({ signal: expect.any(AbortSignal) }),
			),
		);
		expect(await screen.findByText(memory.memoryContent)).toBeVisible();
		expect(screen.getByText("ability")).toBeVisible();

		fireEvent.click(screen.getByRole("checkbox", { name: "From all chapters" }));
		await waitFor(() =>
			expect(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).toHaveBeenCalledWith(
				"group-1",
				{ skip: 0, limit: 20, memoryTypes: undefined },
				expect.objectContaining({ signal: expect.any(AbortSignal) }),
			),
		);

		selectOption("Type", "Event");
		await waitFor(() =>
			expect(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).toHaveBeenLastCalledWith(
				"group-1",
				{ skip: 0, limit: 20, memoryTypes: ["event"] },
				expect.objectContaining({ signal: expect.any(AbortSignal) }),
			),
		);

		fireEvent.click(screen.getByRole("button", { name: "Refresh memories" }));
		await waitFor(() =>
			expect(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).toHaveBeenCalledTimes(3),
		);
		expect(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).toHaveBeenLastCalledWith(
			"group-1",
			{ skip: 0, limit: 20, memoryTypes: ["event"] },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("creates and selects the first memory group", async () => {
		vi.mocked(readMemoryGroupsMemoryGroupsGet).mockResolvedValueOnce({
			status: 200,
			data: [],
			headers: new Headers(),
		});
		const createdGroup: MemoryGroup = {
			memoryGroupId: "group-2",
			memoryGroupName: "Japanese glossary",
			memoryLanguage: "ja",
			novelId: "novel-1",
		};
		vi.mocked(addMemoryGroupMemoryGroupsPost).mockResolvedValueOnce({
			status: 200,
			data: createdGroup,
			headers: new Headers(),
		});
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId={null}
				chapterNum={null}
				chapterContentId={null}
			/>,
		);

		fireEvent.click(await screen.findByRole("button", { name: "Create memory group" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Name" }), {
			target: { value: "  Japanese glossary  " },
		});
		await waitFor(() =>
			expect(screen.getByRole("combobox", { name: "Language" })).toBeEnabled(),
		);
		selectOption("Language", "Japanese");
		fireEvent.click(
			within(screen.getByRole("dialog", { name: "Create memory group" })).getByRole(
				"button",
				{
					name: "Create memory group",
				},
			),
		);

		await waitFor(() =>
			expect(addMemoryGroupMemoryGroupsPost).toHaveBeenCalledWith({
				memoryGroupName: "Japanese glossary",
				memoryLanguage: "ja",
				novelId: "novel-1",
			}),
		);
		expect(
			await screen.findByRole("button", { name: /Memory group.*Japanese glossary/ }),
		).toBeVisible();
	});

	it("keeps a view's search when switching to another view and back", async () => {
		vi.mocked(readConventionsMemoryGroupsMemoryGroupIdConventionsGet).mockResolvedValue({
			data: { count: 0, rows: [] },
			status: 200,
			headers: new Headers(),
		});
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
		await selectView("Glossary");
		fireEvent.change(await screen.findByRole("textbox", { name: "Search terms" }), {
			target: { value: "林" },
		});

		await selectView("Conventions");
		expect(await screen.findByText("No conventions")).toBeVisible();
		await selectView("Glossary");

		expect(screen.getByRole("textbox", { name: "Search terms" })).toHaveValue("林");
	});

	it("edits memory content and reloads the visible memory query", async () => {
		vi.mocked(editMemoryContentMemoriesMemoryIdContentPatch).mockResolvedValueOnce({
			status: 200,
			data: { ...memory, memoryContent: "Updated memory" },
			headers: new Headers(),
		});
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
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
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
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

	it("keeps glossary-specific actions out of the all-memories view", async () => {
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
		await screen.findByText(memory.memoryContent);

		openMenu("Memory actions");

		expect(
			screen.queryByRole("menuitem", { name: "Edit associated terms" }),
		).not.toBeInTheDocument();
	});

	it("confirms memory deletion before reloading the visible query", async () => {
		vi.mocked(removeMemoryMemoriesMemoryIdDelete).mockResolvedValueOnce({
			status: 204,
			data: undefined,
			headers: new Headers(),
		});
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
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
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-13"
				chapterNum={13}
				chapterContentId="content-13"
			/>,
		);
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
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId={null}
				chapterNum={null}
				chapterContentId={null}
			/>,
		);
		fireEvent.click(await screen.findByRole("checkbox", { name: "From all chapters" }));
		await screen.findByText(memory.memoryContent);

		openMenu("Memory actions");
		expect(
			await screen.findByRole("menuitem", { name: "Expire at current chapter" }),
		).toHaveAttribute("data-disabled");
	});
});
