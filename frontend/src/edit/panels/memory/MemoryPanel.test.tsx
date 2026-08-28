import {
	addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost,
	addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost,
	addMemoryGroupMemoryGroupsPost,
	editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch,
	editGlossaryTermReviewStatusMemoryGroupsMemoryGroupIdGlossaryTermsTermIdReviewStatusPatch,
	editMemoryContentMemoriesMemoryIdContentPatch,
	editMemoryExpirationMemoriesMemoryIdExpirationPatch,
	editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch,
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
	readAllLanguagesLanguagesGet,
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet,
	readMemoryGroupsMemoryGroupsGet,
	removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete,
	removeMemoryMemoriesMemoryIdDelete,
	replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut,
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
	addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost: vi.fn(),
	addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost: vi.fn(),
	addMemoryGroupMemoryGroupsPost: vi.fn(),
	editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch: vi.fn(),
	editGlossaryTermReviewStatusMemoryGroupsMemoryGroupIdGlossaryTermsTermIdReviewStatusPatch:
		vi.fn(),
	editMemoryContentMemoriesMemoryIdContentPatch: vi.fn(),
	editMemoryExpirationMemoriesMemoryIdExpirationPatch: vi.fn(),
	editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch: vi.fn(),
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet: vi.fn(),
	readAllLanguagesLanguagesGet: vi.fn(),
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet: vi.fn(),
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet: vi.fn(),
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet: vi.fn(),
	readMemoryGroupsMemoryGroupsGet: vi.fn(),
	removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete: vi.fn(),
	removeMemoryMemoriesMemoryIdDelete: vi.fn(),
	replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut: vi.fn(),
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
};

const glossaryMemory: GlossaryMemory = {
	memory,
	terms: [
		{ reviewStatus: "approved", term: "林凡", termId: "term-1" },
		{ reviewStatus: "pending", term: "青阳镇", termId: "term-2" },
	],
};

function selectOption(label: string, optionName: string) {
	const select = screen.getByRole("combobox", { name: label });
	fireEvent.pointerDown(select, { button: 0, ctrlKey: false, pointerType: "mouse" });
	fireEvent.click(screen.getByRole("option", { name: optionName }));
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

	it("searches scoped terms and loads an expanded term independently", async () => {
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");

		await screen.findByRole("button", { name: /14 memories/ });
		expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenCalledWith(
			"group-1",
			{ skip: 0, limit: 20, chapterId: "chapter-12", search: undefined },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		fireEvent.change(screen.getByRole("textbox", { name: "Search terms" }), {
			target: { value: "Lin" },
		});
		await waitFor(() =>
			expect(
				readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
			).toHaveBeenLastCalledWith(
				"group-1",
				{ skip: 0, limit: 20, chapterId: "chapter-12", search: "Lin" },
				expect.objectContaining({ signal: expect.any(AbortSignal) }),
			),
		);

		fireEvent.click(await screen.findByRole("button", { name: /14 memories/ }));
		expect(await screen.findByText("青阳镇")).toBeVisible();
		expect(
			readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
		).toHaveBeenCalledWith(
			"group-1",
			"term-1",
			{ skip: 0, limit: 10, chapterId: "chapter-12" },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		fireEvent.click(screen.getByRole("button", { name: "Refresh memories for 林凡" }));
		await waitFor(() =>
			expect(
				readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
			).toHaveBeenCalledTimes(2),
		);

		fireEvent.click(screen.getByRole("switch", { name: "Show all terms" }));
		await waitFor(() =>
			expect(
				readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
			).toHaveBeenLastCalledWith(
				"group-1",
				{ skip: 0, limit: 20, chapterId: undefined, search: "Lin" },
				expect.objectContaining({ signal: expect.any(AbortSignal) }),
			),
		);
		expect(await screen.findByRole("button", { name: /14 memories/ })).toHaveAttribute(
			"aria-expanded",
			"false",
		);

		fireEvent.click(screen.getByRole("button", { name: "Refresh glossary terms" }));
		await waitFor(() =>
			expect(
				readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
			).toHaveBeenCalledTimes(4),
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

	it("creates a glossary term and refreshes the current term query", async () => {
		vi.mocked(addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost).mockResolvedValueOnce({
			status: 200,
			data: { reviewStatus: "pending", term: "周明瑞", termId: "term-created" },
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
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		await screen.findByText("林凡");

		fireEvent.click(screen.getByRole("button", { name: "New term" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Term" }), {
			target: { value: "  周明瑞  " },
		});
		fireEvent.click(screen.getByRole("button", { name: "Create term" }));

		await waitFor(() =>
			expect(addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost).toHaveBeenCalledWith(
				"group-1",
				{ term: "周明瑞" },
			),
		);
		await waitFor(() =>
			expect(
				readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
			).toHaveBeenCalledTimes(2),
		);
		expect(screen.queryByRole("dialog", { name: "New glossary term" })).not.toBeInTheDocument();
	});

	it("creates a glossary memory with the row term preselected", async () => {
		vi.mocked(
			addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost,
		).mockResolvedValueOnce({ status: 200, data: glossaryMemory, headers: new Headers() });
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		fireEvent.click(await screen.findByRole("button", { name: "Add memory for 林凡" }));

		expect(screen.getByRole("button", { name: "Remove 林凡" })).toBeVisible();
		fireEvent.change(screen.getByRole("textbox", { name: "Content" }), {
			target: { value: "  Lin Fan joined the inner sect.  " },
		});
		fireEvent.click(screen.getByRole("button", { name: "Create memory" }));

		await waitFor(() =>
			expect(
				addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost,
			).toHaveBeenCalledWith("group-1", {
				chapterContentId: "content-12",
				chapterId: "chapter-12",
				memoryContent: "Lin Fan joined the inner sect.",
				memoryType: "fact",
				scope: null,
				termIds: ["term-1"],
			}),
		);
		expect(
			screen.queryByRole("dialog", { name: "New glossary memory" }),
		).not.toBeInTheDocument();
	});

	it("keeps an unsuccessful glossary-memory draft open", async () => {
		vi.mocked(
			addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost,
		).mockRejectedValueOnce(new Error("offline"));
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		fireEvent.click(await screen.findByRole("button", { name: "Add memory for 林凡" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Content" }), {
			target: { value: "Keep this draft" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Create memory" }));

		expect(await screen.findByText("offline")).toBeVisible();
		expect(screen.getByRole("dialog", { name: "New glossary memory" })).toBeVisible();
		expect(screen.getByRole("textbox", { name: "Content" })).toHaveValue("Keep this draft");
	});

	it("disables memory creation until saved chapter content is available", async () => {
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId={null}
			/>,
		);
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");

		expect(await screen.findByRole("button", { name: "Add memory for 林凡" })).toBeDisabled();
	});

	it("renames a glossary term and reloads the current term query", async () => {
		vi.mocked(
			editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch,
		).mockResolvedValueOnce({
			status: 200,
			data: { reviewStatus: "approved", term: "林凡更新", termId: "term-1" },
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
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		await screen.findByRole("button", { name: "Actions for 林凡" });

		openMenu("Actions for 林凡");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Term" }), {
			target: { value: "  林凡更新  " },
		});
		fireEvent.click(screen.getByRole("button", { name: "Save term" }));

		await waitFor(() =>
			expect(
				editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch,
			).toHaveBeenCalledWith("group-1", "term-1", { term: "林凡更新" }),
		);
		await waitFor(() =>
			expect(
				readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
			).toHaveBeenCalledTimes(2),
		);
		expect(
			screen.queryByRole("dialog", { name: "Rename glossary term" }),
		).not.toBeInTheDocument();
	});

	it("preserves a glossary term rename after a conflict", async () => {
		vi.mocked(
			editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch,
		).mockResolvedValueOnce({
			status: 409,
			data: { detail: "Glossary term already exists." },
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
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		await screen.findByRole("button", { name: "Actions for 林凡" });

		openMenu("Actions for 林凡");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Term" }), {
			target: { value: "Existing term" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Save term" }));

		expect(await screen.findByText("Glossary term already exists.")).toBeVisible();
		expect(screen.getByRole("textbox", { name: "Term" })).toHaveValue("Existing term");
		expect(screen.getByRole("dialog", { name: "Rename glossary term" })).toBeVisible();
	});

	it("keeps a failed term deletion open and explains its effect", async () => {
		vi.mocked(
			removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete,
		).mockRejectedValueOnce(new Error("delete unavailable"));
		render(
			<MemoryPanel
				novelId="novel-1"
				chapterId="chapter-12"
				chapterNum={12}
				chapterContentId="content-12"
			/>,
		);
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		await screen.findByRole("button", { name: "Actions for 林凡" });

		openMenu("Actions for 林凡");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }));
		expect(
			screen.getByText(/associated memories themselves will not be deleted/i),
		).toBeVisible();
		fireEvent.click(screen.getByRole("button", { name: "Delete term" }));

		expect(await screen.findByText("delete unavailable")).toBeVisible();
		expect(
			removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete,
		).toHaveBeenCalledWith("group-1", "term-1");
		expect(screen.getByRole("dialog", { name: "Delete glossary term?" })).toBeVisible();
	});

	it("changes a glossary term review status from its action menu", async () => {
		vi.mocked(
			editGlossaryTermReviewStatusMemoryGroupsMemoryGroupIdGlossaryTermsTermIdReviewStatusPatch,
		).mockResolvedValueOnce({
			status: 200,
			data: { reviewStatus: "pending", term: "林凡", termId: "term-1" },
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
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		await screen.findByRole("button", { name: "Actions for 林凡" });

		openMenu("Actions for 林凡");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Review status" }));
		fireEvent.click(await screen.findByRole("menuitemradio", { name: "Pending" }));

		await waitFor(() =>
			expect(
				editGlossaryTermReviewStatusMemoryGroupsMemoryGroupIdGlossaryTermsTermIdReviewStatusPatch,
			).toHaveBeenCalledWith("group-1", "term-1", { reviewStatus: "pending" }),
		);
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
		fireEvent.click(await screen.findByRole("menuitem", { name: "Edit content" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Content" }), {
			target: { value: "  Updated memory  " },
		});
		fireEvent.click(screen.getByRole("button", { name: "Save content" }));

		await waitFor(() =>
			expect(editMemoryContentMemoriesMemoryIdContentPatch).toHaveBeenCalledWith("memory-1", {
				memoryContent: "Updated memory",
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

	it("replaces memory associations and reloads nested memories and terms", async () => {
		vi.mocked(
			replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut,
		).mockResolvedValueOnce({
			status: 200,
			data: [{ reviewStatus: "approved", term: "林凡", termId: "term-1" }],
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
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");
		fireEvent.click(await screen.findByRole("button", { name: /14 memories/ }));
		await screen.findByRole("button", { name: "Memory actions" });

		openMenu("Memory actions");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Edit associated terms" }));
		fireEvent.click(screen.getByRole("button", { name: "Remove 青阳镇" }));
		fireEvent.click(screen.getByRole("button", { name: "Save terms" }));

		await waitFor(() =>
			expect(
				replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut,
			).toHaveBeenCalledWith("group-1", "memory-1", { termIds: ["term-1"] }),
		);
		await waitFor(() =>
			expect(
				readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
			).toHaveBeenCalledTimes(2),
		);
		expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenLastCalledWith(
			"group-1",
			{ skip: 0, limit: 20, chapterId: "chapter-12", search: undefined },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
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
