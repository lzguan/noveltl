import {
	addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost,
	addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost,
	editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch,
	editGlossaryTermReviewStatusMemoryGroupsMemoryGroupIdGlossaryTermsTermIdReviewStatusPatch,
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
	readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet,
	removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete,
	replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut,
} from "@/api/endpoints/default/default";
import type { GlossaryMemory, GlossaryTermSummary, Memory } from "@/api/models";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { GlossaryBrowser } from "./GlossaryBrowser";

// Replace HTTP only; keep the browser, its hooks, rows, and dialogs real.
vi.mock("@/api/endpoints/default/default", () => ({
	addGlossaryMemoryMemoryGroupsMemoryGroupIdGlossaryMemoriesPost: vi.fn(),
	addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost: vi.fn(),
	editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch: vi.fn(),
	editGlossaryTermReviewStatusMemoryGroupsMemoryGroupIdGlossaryTermsTermIdReviewStatusPatch:
		vi.fn(),
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet: vi.fn(),
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet: vi.fn(),
	readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet: vi.fn(),
	removeGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdDelete: vi.fn(),
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

function openMenu(label: string) {
	const trigger = screen.getByRole("button", { name: label });
	fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false, pointerType: "mouse" });
}

function renderBrowser(chapterContentId: string | null = "content-12") {
	return render(
		<GlossaryBrowser
			memoryGroupId="group-1"
			chapterId="chapter-12"
			chapterNum={12}
			chapterContentId={chapterContentId}
			view="glossary"
		/>,
	);
}

describe("GlossaryBrowser", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).mockResolvedValue({
			status: 200,
			data: [],
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

	it("searches scoped terms and loads an expanded term independently", async () => {
		renderBrowser();

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

	it("creates a glossary term and refreshes the current term query", async () => {
		vi.mocked(addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost).mockResolvedValueOnce({
			status: 200,
			data: {
				reviewStatus: "pending",
				term: "周明瑞",
				termId: "term-created",
				termKind: "person",
			},
			headers: new Headers(),
		});
		renderBrowser();
		await screen.findByText("林凡");

		fireEvent.click(screen.getByRole("button", { name: "New term" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Term" }), {
			target: { value: "  周明瑞  " },
		});
		selectOption("Kind", "Person");
		fireEvent.click(screen.getByRole("button", { name: "Create term" }));

		await waitFor(() =>
			expect(addGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsPost).toHaveBeenCalledWith(
				"group-1",
				{ term: "周明瑞", termKind: "person" },
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
		renderBrowser();
		fireEvent.click(await screen.findByRole("button", { name: "Add memory for 林凡" }));

		expect(screen.getByRole("button", { name: "Remove 林凡" })).toBeVisible();
		fireEvent.change(screen.getByRole("textbox", { name: "Content" }), {
			target: { value: "  Lin Fan joined the inner sect.  " },
		});
		fireEvent.change(screen.getByRole("textbox", { name: "Mark (optional)" }), {
			target: { value: "  membership  " },
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
				mark: "membership",
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
		renderBrowser();
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
		renderBrowser(null);

		expect(await screen.findByRole("button", { name: "Add memory for 林凡" })).toBeDisabled();
	});

	it("renames a glossary term and reloads the current term query", async () => {
		vi.mocked(
			editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch,
		).mockResolvedValueOnce({
			status: 200,
			data: {
				reviewStatus: "approved",
				term: "林凡更新",
				termId: "term-1",
				termKind: "place",
			},
			headers: new Headers(),
		});
		renderBrowser();
		await screen.findByRole("button", { name: "Actions for 林凡" });

		openMenu("Actions for 林凡");
		fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }));
		fireEvent.change(screen.getByRole("textbox", { name: "Term" }), {
			target: { value: "  林凡更新  " },
		});
		selectOption("Kind", "Place");
		fireEvent.click(screen.getByRole("button", { name: "Save term" }));

		await waitFor(() =>
			expect(
				editGlossaryTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdPatch,
			).toHaveBeenCalledWith("group-1", "term-1", {
				term: "林凡更新",
				termKind: "place",
			}),
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
		renderBrowser();
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
		renderBrowser();
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
			data: {
				reviewStatus: "pending",
				term: "林凡",
				termId: "term-1",
				termKind: "person",
			},
			headers: new Headers(),
		});
		renderBrowser();
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

	it("replaces memory associations and reloads nested memories and terms", async () => {
		vi.mocked(
			replaceGlossaryMemoryTermsMemoryGroupsMemoryGroupIdGlossaryMemoriesMemoryIdTermsPut,
		).mockResolvedValueOnce({
			status: 200,
			data: [
				{
					reviewStatus: "approved",
					term: "林凡",
					termId: "term-1",
					termKind: "person",
				},
			],
			headers: new Headers(),
		});
		renderBrowser();
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
});
