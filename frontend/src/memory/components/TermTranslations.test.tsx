import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, expect, it, vi } from "vitest";
import {
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
	readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet,
	putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut,
	removeTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdDelete,
	editTermTranslationReviewStatusMemoryGroupsMemoryGroupIdTranslationsTermIdReviewStatusPatch,
} from "@/api/endpoints/default/default";
import type { GlossaryTermSummary, TermTranslationRead } from "@/api/models";
import { GlossaryBrowser } from "./GlossaryBrowser";

// Replace HTTP only; keep search, pagination, batch loading, and editing real.
vi.mock("@/api/endpoints/default/default", async (importOriginal) => ({
	...(await importOriginal<typeof import("@/api/endpoints/default/default")>()),
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet: vi.fn(),
	readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet: vi.fn(),
	putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut: vi.fn(),
	removeTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdDelete: vi.fn(),
	editTermTranslationReviewStatusMemoryGroupsMemoryGroupIdTranslationsTermIdReviewStatusPatch:
		vi.fn(),
}));

const term: GlossaryTermSummary = {
	termId: "term-1",
	term: "Alpha",
	termKind: "person",
	reviewStatus: "pending",
	associatedMemoryCount: 2,
};
const mapping: TermTranslationRead = {
	termId: term.termId,
	translation: "Existing rendering",
	reviewStatus: "approved",
	creatorType: "agent",
	createdAt: "2026-11-02T00:00:00Z",
	updatedAt: "2026-11-02T00:00:00Z",
};
function ok<T>(data: T) {
	return { data, status: 200 as const, headers: new Headers() };
}
function browser(view: "glossary" | "translations" = "translations") {
	return render(
		<GlossaryBrowser
			memoryGroupId="group-1"
			chapterId={view === "glossary" ? "chapter-1" : null}
			chapterNum={null}
			chapterContentId={null}
			view={view}
		/>,
	);
}

beforeAll(() => {
	class Observer implements ResizeObserver {
		disconnect() {}
		observe() {}
		unobserve() {}
	}
	vi.stubGlobal("ResizeObserver", Observer);
});
beforeEach(() => {
	vi.resetAllMocks();
	vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).mockResolvedValue(
		ok({ count: 1, rows: [term] }),
	);
	vi.mocked(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).mockResolvedValue(
		ok([mapping]),
	);
});

it("loads one batch after the term page and saves locally without refetching terms", async () => {
	vi.mocked(putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut).mockResolvedValue(
		ok({
			...mapping,
			translation: "Human rendering",
			creatorType: "user",
		}),
	);
	browser();
	expect(await screen.findByText("Existing rendering")).toBeVisible();
	expect(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).toHaveBeenCalledOnce();
	expect(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).toHaveBeenCalledWith(
		"group-1",
		{ termIds: ["term-1"] },
		expect.objectContaining({ signal: expect.any(AbortSignal) }),
	);
	fireEvent.click(screen.getByRole("button", { name: "Edit translation for Alpha" }));
	fireEvent.change(screen.getByRole("textbox", { name: "Translation for Alpha" }), {
		target: { value: " Human rendering " },
	});
	fireEvent.click(screen.getByRole("button", { name: "Save translation" }));
	expect(await screen.findByText("Human rendering")).toBeVisible();
	expect(screen.getByText("Edited by user")).toBeVisible();
	expect(screen.getByText("approved")).toBeVisible();
	expect(putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut).toHaveBeenCalledWith(
		"group-1",
		"term-1",
		{ translation: "Human rendering" },
	);
	expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenCalledOnce();
});

it("supports missing mappings, cancel, and keeping a failed save's draft", async () => {
	vi.mocked(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).mockResolvedValue(
		ok([]),
	);
	vi.mocked(putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut).mockResolvedValue({
		status: 404,
		data: { detail: "No edit permission" },
		headers: new Headers(),
	});
	browser();
	fireEvent.click(await screen.findByRole("button", { name: "Add translation for Alpha" }));
	fireEvent.change(screen.getByRole("textbox", { name: "Translation for Alpha" }), {
		target: { value: "Discard me" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
	expect(putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut).not.toHaveBeenCalled();
	fireEvent.click(screen.getByRole("button", { name: "Add translation for Alpha" }));
	expect(screen.getByRole("textbox", { name: "Translation for Alpha" })).toHaveValue("");
	fireEvent.click(screen.getByRole("button", { name: "Save translation" }));
	expect(screen.getByRole("alert")).toHaveTextContent("Translation is required.");
	expect(putTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdPut).not.toHaveBeenCalled();
	fireEvent.change(screen.getByRole("textbox", { name: "Translation for Alpha" }), {
		target: { value: "Keep this draft" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Save translation" }));
	await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("No edit permission"));
	expect(screen.getByRole("textbox", { name: "Translation for Alpha" })).toHaveValue(
		"Keep this draft",
	);
});

it("keeps terms visible when batch loading fails and allows retry", async () => {
	vi.mocked(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet)
		.mockResolvedValueOnce({
			status: 404,
			data: { detail: "Unavailable" },
			headers: new Headers(),
		})
		.mockResolvedValueOnce(ok([mapping]));
	browser();
	expect(await screen.findByRole("alert")).toHaveTextContent("Unavailable");
	expect(screen.getByText("Alpha")).toBeVisible();
	fireEvent.click(screen.getByRole("button", { name: "Retry translations" }));
	expect(await screen.findByText("Existing rendering")).toBeVisible();
});

it("ignores an obsolete translation batch after the search changes", async () => {
	let finishOld: (value: ReturnType<typeof ok<TermTranslationRead[]>>) => void = () => {
		throw new Error("Request not started");
	};
	const oldBatch = new Promise<ReturnType<typeof ok<TermTranslationRead[]>>>((resolve) => {
		finishOld = resolve;
	});
	vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet)
		.mockResolvedValueOnce(ok({ count: 1, rows: [term] }))
		.mockResolvedValueOnce(
			ok({ count: 1, rows: [{ ...term, termId: "term-2", term: "Beta" }] }),
		);
	vi.mocked(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet)
		.mockReturnValueOnce(oldBatch)
		.mockResolvedValueOnce(
			ok([{ ...mapping, termId: "term-2", translation: "Beta rendering" }]),
		);
	browser();
	await waitFor(() =>
		expect(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).toHaveBeenCalledOnce(),
	);
	fireEvent.change(screen.getByRole("textbox", { name: "Search terms" }), {
		target: { value: "Beta" },
	});
	expect(await screen.findByText("Beta rendering")).toBeVisible();
	await act(async () => finishOld(ok([mapping])));
	expect(screen.getByText("Beta rendering")).toBeVisible();
	expect(screen.queryByText("Existing rendering")).not.toBeInTheDocument();
});

it("fetches the next term page before requesting that page's translations", async () => {
	vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet)
		.mockResolvedValueOnce(ok({ count: 21, rows: [term] }))
		.mockResolvedValueOnce(
			ok({ count: 21, rows: [{ ...term, termId: "term-2", term: "Beta" }] }),
		);
	vi.mocked(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet)
		.mockResolvedValueOnce(ok([mapping]))
		.mockResolvedValueOnce(ok([]));
	browser();
	expect(await screen.findByText("Existing rendering")).toBeVisible();
	fireEvent.click(screen.getByRole("button", { name: "Next" }));
	expect(await screen.findByText("Beta")).toBeVisible();
	await waitFor(() =>
		expect(
			readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet,
		).toHaveBeenNthCalledWith(2, "group-1", { termIds: ["term-2"] }, expect.any(Object)),
	);
	expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenLastCalledWith(
		"group-1",
		expect.objectContaining({ skip: 20 }),
		expect.any(Object),
	);
});

it("shows the translation beneath its source in the collapsed glossary row", async () => {
	browser("glossary");
	const preview = await screen.findByText("Existing rendering");
	expect(preview).toBeVisible();
	expect(preview.closest("button")).toHaveTextContent("Alpha");
});

it("does not request translations for an empty term page", async () => {
	vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).mockResolvedValue(
		ok({ count: 0, rows: [] }),
	);
	browser();
	expect(await screen.findByText("No terms match this search.")).toBeVisible();
	expect(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).not.toHaveBeenCalled();
});

it("keeps a failed deletion visible and removes only the mapping after a successful retry", async () => {
	vi.mocked(removeTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdDelete)
		.mockResolvedValueOnce({
			status: 404,
			data: { detail: "No edit permission" },
			headers: new Headers(),
		})
		.mockResolvedValueOnce({ status: 204, data: undefined, headers: new Headers() });
	browser();
	const remove = await screen.findByRole("button", { name: "Delete translation for Alpha" });
	fireEvent.click(remove);
	expect(await screen.findByRole("alert")).toHaveTextContent("No edit permission");
	expect(screen.getByText("Existing rendering")).toBeVisible();
	fireEvent.click(remove);
	expect(await screen.findByText("Not translated")).toBeVisible();
	expect(screen.getByText("Alpha")).toBeVisible();
	expect(screen.getByRole("button", { name: "Add translation for Alpha" })).toBeEnabled();
	expect(
		screen.queryByRole("button", { name: "Delete translation for Alpha" }),
	).not.toBeInTheDocument();
	expect(screen.queryByRole("alert")).not.toBeInTheDocument();
	expect(
		removeTermTranslationMemoryGroupsMemoryGroupIdTranslationsTermIdDelete,
	).toHaveBeenLastCalledWith("group-1", "term-1");
	expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenCalledOnce();
	expect(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).toHaveBeenCalledOnce();
});

it("reviews translations locally and retains the current status when a review fails", async () => {
	vi.mocked(
		editTermTranslationReviewStatusMemoryGroupsMemoryGroupIdTranslationsTermIdReviewStatusPatch,
	)
		.mockResolvedValueOnce({
			status: 404,
			data: { detail: "No edit permission" },
			headers: new Headers(),
		})
		.mockResolvedValueOnce(ok({ ...mapping, reviewStatus: "rejected" }))
		.mockResolvedValueOnce(ok(mapping));
	browser();
	const approve = await screen.findByRole("button", { name: "Approve translation for Alpha" });
	const reject = screen.getByRole("button", { name: "Reject translation for Alpha" });
	expect(approve).toBeDisabled();
	fireEvent.click(reject);
	expect(await screen.findByRole("alert")).toHaveTextContent("No edit permission");
	expect(screen.getByText("approved")).toBeVisible();
	fireEvent.click(reject);
	expect(await screen.findByText("rejected")).toBeVisible();
	expect(reject).toBeDisabled();
	expect(screen.queryByRole("alert")).not.toBeInTheDocument();
	expect(
		editTermTranslationReviewStatusMemoryGroupsMemoryGroupIdTranslationsTermIdReviewStatusPatch,
	).toHaveBeenLastCalledWith("group-1", "term-1", { reviewStatus: "rejected" });
	fireEvent.click(approve);
	expect(await screen.findByText("approved")).toBeVisible();
	expect(
		editTermTranslationReviewStatusMemoryGroupsMemoryGroupIdTranslationsTermIdReviewStatusPatch,
	).toHaveBeenLastCalledWith("group-1", "term-1", { reviewStatus: "approved" });
	expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenCalledOnce();
	expect(readTermTranslationsMemoryGroupsMemoryGroupIdTranslationsGet).toHaveBeenCalledOnce();
});
