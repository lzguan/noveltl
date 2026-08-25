import {
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet,
	readMemoryGroupsMemoryGroupsGet,
} from "@/api/endpoints/default/default";
import type { GlossaryMemory, GlossaryTermSummary, Memory, MemoryGroup } from "@/api/models";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryPanel } from "./MemoryPanel";

vi.mock("@/api/endpoints/default/default", () => ({
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet: vi.fn(),
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
		render(<MemoryPanel novelId="novel-1" chapterId="chapter-12" />);

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
	});

	it("searches scoped terms and loads an expanded term independently", async () => {
		render(<MemoryPanel novelId="novel-1" chapterId="chapter-12" />);
		await screen.findByRole("combobox", { name: "Plugin" });
		selectOption("Plugin", "Glossary");

		await screen.findByRole("button", { name: /林凡/ });
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

		fireEvent.click(await screen.findByRole("button", { name: /林凡/ }));
		expect(await screen.findByText("青阳镇")).toBeVisible();
		expect(
			readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
		).toHaveBeenCalledWith(
			"group-1",
			"term-1",
			{ skip: 0, limit: 10, chapterId: "chapter-12" },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
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
	});
});
