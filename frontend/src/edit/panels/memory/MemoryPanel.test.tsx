import {
	addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost,
	addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost,
	addMemoryGroupMemoryGroupsPost,
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
	readAllLanguagesLanguagesGet,
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet,
	readMemoryGroupsMemoryGroupsGet,
} from "@/api/endpoints/default/default";
import type { GlossaryMemory, GlossaryTermSummary, Memory, MemoryGroup } from "@/api/models";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryPanel } from "./MemoryPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost: vi.fn(),
	addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost: vi.fn(),
	addMemoryGroupMemoryGroupsPost: vi.fn(),
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet: vi.fn(),
	readAllLanguagesLanguagesGet: vi.fn(),
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet: vi.fn(),
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet: vi.fn(),
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet: vi.fn(),
	readMemoryGroupsMemoryGroupsGet: vi.fn(),
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
			<MemoryPanel novelId="novel-1" chapterId="chapter-12" chapterContentId="content-12" />,
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
			<MemoryPanel novelId="novel-1" chapterId="chapter-12" chapterContentId="content-12" />,
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
		render(<MemoryPanel novelId="novel-1" chapterId={null} chapterContentId={null} />);

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
		expect(await screen.findByRole("combobox", { name: "Memory group" })).toHaveTextContent(
			"Japanese glossary",
		);
	});

	it("creates a glossary term and refreshes the current term query", async () => {
		vi.mocked(addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost).mockResolvedValueOnce({
			status: 200,
			data: { reviewStatus: "pending", term: "周明瑞", termId: "term-created" },
			headers: new Headers(),
		});
		render(
			<MemoryPanel novelId="novel-1" chapterId="chapter-12" chapterContentId="content-12" />,
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
			<MemoryPanel novelId="novel-1" chapterId="chapter-12" chapterContentId="content-12" />,
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
			<MemoryPanel novelId="novel-1" chapterId="chapter-12" chapterContentId="content-12" />,
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
		render(<MemoryPanel novelId="novel-1" chapterId="chapter-12" chapterContentId={null} />);
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");

		expect(await screen.findByRole("button", { name: "Add memory for 林凡" })).toBeDisabled();
	});
});
