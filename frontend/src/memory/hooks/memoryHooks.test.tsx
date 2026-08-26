import {
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet,
	readMemoryGroupsMemoryGroupsGet,
} from "@/api/endpoints/default/default";
import {
	Creator,
	MemoryType,
	ReviewStatus,
	Scope,
	type GlossaryMemory,
	type GlossaryTerm,
	type GlossaryTermSummary,
	type Memory,
	type MemoryGroup,
} from "@/api/models";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGlossaryMemoryForm } from "./useGlossaryMemoryForm";
import { GLOSSARY_TERM_PAGE_SIZE, useGlossaryTerms } from "./useGlossaryTerms";
import { MEMORY_PAGE_SIZE, useMemoryBrowser } from "./useMemoryBrowser";
import { useMemoryGroups } from "./useMemoryGroups";
import { TERM_MEMORY_PAGE_SIZE, useTermMemories } from "./useTermMemories";

vi.mock("@/api/endpoints/default/default", () => ({
	readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet: vi.fn(),
	readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet: vi.fn(),
	readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet: vi.fn(),
	readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet: vi.fn(),
	readMemoryGroupsMemoryGroupsGet: vi.fn(),
}));

const groupOne: MemoryGroup = {
	memoryGroupId: "group-1",
	memoryGroupName: "Main",
	memoryLanguage: "en",
	novelId: "novel-1",
};

const groupTwo: MemoryGroup = {
	memoryGroupId: "group-2",
	memoryGroupName: "Alternative",
	memoryLanguage: "en",
	novelId: "novel-1",
};

const termOne: GlossaryTerm = {
	termId: "term-1",
	term: "林凡",
	reviewStatus: ReviewStatus.pending,
};

const termTwo: GlossaryTerm = {
	termId: "term-2",
	term: "林家",
	reviewStatus: ReviewStatus.approved,
};

function memory(memoryId: string): Memory {
	return {
		creatorType: Creator.user,
		memoryContent: `Memory ${memoryId}`,
		memoryEndNum: null,
		memoryId,
		memoryReviewStatus: ReviewStatus.pending,
		memoryStartNum: 1,
		memoryType: MemoryType.fact,
		pluginName: "glossary",
		supersedesMemoryId: null,
	};
}

function glossaryMemory(memoryId: string): GlossaryMemory {
	return { memory: memory(memoryId), terms: [termOne] };
}

function glossaryTermSummary(termId: string): GlossaryTermSummary {
	return {
		associatedMemoryCount: 1,
		reviewStatus: ReviewStatus.pending,
		term: `Term ${termId}`,
		termId,
	};
}

describe("memory hooks", () => {
	beforeEach(() => vi.clearAllMocks());

	it("loads memory groups only when requested and preserves a valid selection on reload", async () => {
		vi.mocked(readMemoryGroupsMemoryGroupsGet)
			.mockResolvedValueOnce({
				status: 200,
				data: [groupOne, groupTwo],
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: [groupOne, groupTwo],
				headers: new Headers(),
			});
		const { result } = renderHook(() => useMemoryGroups("novel-1"));

		expect(result.current.groups).toEqual({ status: "idle" });
		expect(readMemoryGroupsMemoryGroupsGet).not.toHaveBeenCalled();

		act(() => result.current.loadGroups());
		expect(result.current.groups).toEqual({ status: "loading" });
		await waitFor(() => expect(result.current.groups.status).toBe("ready"));
		expect(result.current.selectedGroupId).toBe(groupOne.memoryGroupId);
		expect(readMemoryGroupsMemoryGroupsGet).toHaveBeenCalledWith(
			{ novelId: "novel-1" },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		act(() => result.current.selectGroup(groupTwo.memoryGroupId));
		act(() => result.current.reloadGroups());
		await waitFor(() => expect(readMemoryGroupsMemoryGroupsGet).toHaveBeenCalledTimes(2));
		await waitFor(() => expect(result.current.groups.status).toBe("ready"));
		expect(result.current.selectedGroupId).toBe(groupTwo.memoryGroupId);
	});

	it("adds a group to the loaded options and selects it", () => {
		const { result } = renderHook(() => useMemoryGroups("novel-1"));

		act(() => result.current.addAndSelectGroup(groupTwo));

		expect(result.current.groups).toEqual({ status: "ready", data: [groupTwo] });
		expect(result.current.selectedGroupId).toBe(groupTwo.memoryGroupId);
	});

	it("loads and paginates chapter memories from explicit commands", async () => {
		vi.mocked(readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet)
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 21, rows: [memory("memory-1")] },
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 21, rows: [memory("memory-21")] },
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 20, rows: [memory("memory-1")] },
				headers: new Headers(),
			});
		const { result } = renderHook(() => useMemoryBrowser("group-1", "chapter-1"));

		expect(result.current.memories).toEqual({ status: "idle" });
		expect(
			readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
		).not.toHaveBeenCalled();

		act(() => result.current.loadMemories());
		await waitFor(() => expect(result.current.memories.status).toBe("ready"));
		expect(result.current.memories).toEqual({
			status: "ready",
			data: {
				items: [memory("memory-1")],
				start: 1,
				end: 1,
				total: 21,
				hasPrevious: false,
				hasNext: true,
			},
		});

		act(() => result.current.loadNextPage());
		await waitFor(() => {
			if (result.current.memories.status !== "ready") return false;
			return result.current.memories.data.start === 21;
		});
		expect(
			readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
		).toHaveBeenLastCalledWith(
			"group-1",
			"chapter-1",
			{ skip: MEMORY_PAGE_SIZE, limit: MEMORY_PAGE_SIZE, memoryTypes: undefined },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		act(() => result.current.reloadMemoriesAfterDelete());
		await waitFor(() =>
			expect(
				readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
			).toHaveBeenCalledTimes(3),
		);
		expect(
			readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
		).toHaveBeenLastCalledWith(
			"group-1",
			"chapter-1",
			{ skip: 0, limit: MEMORY_PAGE_SIZE, memoryTypes: undefined },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("applies scope and type changes directly and resets pagination", async () => {
		vi.mocked(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).mockResolvedValue({
			status: 200,
			data: { count: 1, rows: [memory("memory-1")] },
			headers: new Headers(),
		});
		const { result } = renderHook(() => useMemoryBrowser("group-1", "chapter-1"));

		act(() => result.current.setFromAllChapters(true));
		await waitFor(() => expect(result.current.memories.status).toBe("ready"));
		expect(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).toHaveBeenLastCalledWith(
			"group-1",
			{ skip: 0, limit: MEMORY_PAGE_SIZE, memoryTypes: undefined },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		act(() => result.current.setMemoryType(MemoryType.event));
		await waitFor(() =>
			expect(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).toHaveBeenCalledTimes(2),
		);
		expect(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).toHaveBeenLastCalledWith(
			"group-1",
			{ skip: 0, limit: MEMORY_PAGE_SIZE, memoryTypes: [MemoryType.event] },
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("does not display a superseded memory request", async () => {
		type ChapterResponse = Awaited<
			ReturnType<
				typeof readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet
			>
		>;
		let resolveChapterRequest: (response: ChapterResponse) => void = () => undefined;
		const chapterRequest = new Promise<ChapterResponse>((resolve) => {
			resolveChapterRequest = resolve;
		});
		vi.mocked(
			readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
		).mockReturnValue(chapterRequest);
		vi.mocked(readMemoriesMemoryGroupsMemoryGroupIdMemoriesGet).mockResolvedValue({
			status: 200,
			data: { count: 1, rows: [memory("all-chapters-memory")] },
			headers: new Headers(),
		});
		const { result } = renderHook(() => useMemoryBrowser("group-1", "chapter-1"));

		act(() => result.current.loadMemories());
		act(() => result.current.setFromAllChapters(true));
		await waitFor(() => expect(result.current.memories.status).toBe("ready"));
		const chapterRequestOptions = vi.mocked(
			readMemoriesAtChapterMemoryGroupsMemoryGroupIdChaptersChapterIdMemoriesGet,
		).mock.calls[0]?.[3];
		expect(chapterRequestOptions?.signal).toHaveProperty("aborted", true);

		await act(async () => {
			resolveChapterRequest({
				status: 200,
				data: { count: 1, rows: [memory("stale-chapter-memory")] },
				headers: new Headers(),
			});
			await chapterRequest;
		});

		expect(result.current.memories).toEqual({
			status: "ready",
			data: {
				items: [memory("all-chapters-memory")],
				start: 1,
				end: 1,
				total: 1,
				hasPrevious: false,
				hasNext: false,
			},
		});
	});

	it("loads and paginates glossary terms from explicit commands", async () => {
		vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet)
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 21, rows: [glossaryTermSummary("term-1")] },
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 21, rows: [glossaryTermSummary("term-21")] },
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 20, rows: [glossaryTermSummary("term-1")] },
				headers: new Headers(),
			});
		const { result } = renderHook(() => useGlossaryTerms("group-1", "chapter-1"));

		expect(result.current.terms).toEqual({ status: "idle" });
		expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).not.toHaveBeenCalled();

		act(() => result.current.loadTerms());
		await waitFor(() => expect(result.current.terms.status).toBe("ready"));
		act(() => result.current.loadNextPage());
		await waitFor(() => {
			if (result.current.terms.status !== "ready") return false;
			return result.current.terms.data.start === 21;
		});

		expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenLastCalledWith(
			"group-1",
			{
				skip: GLOSSARY_TERM_PAGE_SIZE,
				limit: GLOSSARY_TERM_PAGE_SIZE,
				chapterId: "chapter-1",
				search: undefined,
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		act(() => result.current.reloadTermsAfterDelete());
		await waitFor(() =>
			expect(
				readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
			).toHaveBeenCalledTimes(3),
		);
		expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenLastCalledWith(
			"group-1",
			{
				skip: 0,
				limit: GLOSSARY_TERM_PAGE_SIZE,
				chapterId: "chapter-1",
				search: undefined,
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("applies glossary scope and search changes directly and resets pagination", async () => {
		vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).mockResolvedValue({
			status: 200,
			data: { count: 1, rows: [glossaryTermSummary("term-1")] },
			headers: new Headers(),
		});
		const { result } = renderHook(() => useGlossaryTerms("group-1", "chapter-1"));

		act(() => result.current.setSearch("Lin"));
		await waitFor(() => expect(result.current.terms.status).toBe("ready"));
		expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenLastCalledWith(
			"group-1",
			{
				skip: 0,
				limit: GLOSSARY_TERM_PAGE_SIZE,
				chapterId: "chapter-1",
				search: "Lin",
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		act(() => result.current.setShowAllTerms(true));
		await waitFor(() =>
			expect(
				readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
			).toHaveBeenCalledTimes(2),
		);
		expect(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet).toHaveBeenLastCalledWith(
			"group-1",
			{
				skip: 0,
				limit: GLOSSARY_TERM_PAGE_SIZE,
				chapterId: undefined,
				search: "Lin",
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("does not display a superseded glossary term request", async () => {
		type TermsResponse = Awaited<
			ReturnType<typeof readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet>
		>;
		let resolveChapterRequest: (response: TermsResponse) => void = () => undefined;
		const chapterRequest = new Promise<TermsResponse>((resolve) => {
			resolveChapterRequest = resolve;
		});
		vi.mocked(readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet)
			.mockReturnValueOnce(chapterRequest)
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 1, rows: [glossaryTermSummary("all-terms")] },
				headers: new Headers(),
			});
		const { result } = renderHook(() => useGlossaryTerms("group-1", "chapter-1"));

		act(() => result.current.loadTerms());
		act(() => result.current.setShowAllTerms(true));
		await waitFor(() => expect(result.current.terms.status).toBe("ready"));
		const chapterRequestOptions = vi.mocked(
			readGlossaryTermsMemoryGroupsMemoryGroupIdGlossaryTermsGet,
		).mock.calls[0]?.[2];
		expect(chapterRequestOptions?.signal).toHaveProperty("aborted", true);

		await act(async () => {
			resolveChapterRequest({
				status: 200,
				data: { count: 1, rows: [glossaryTermSummary("stale-term")] },
				headers: new Headers(),
			});
			await chapterRequest;
		});

		expect(result.current.terms).toEqual({
			status: "ready",
			data: {
				items: [glossaryTermSummary("all-terms")],
				start: 1,
				end: 1,
				total: 1,
				hasPrevious: false,
				hasNext: false,
			},
		});
	});

	it("loads term memories on expansion and paginates independently", async () => {
		vi.mocked(readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet)
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 11, rows: [glossaryMemory("memory-1")] },
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 11, rows: [glossaryMemory("memory-11")] },
				headers: new Headers(),
			})
			.mockResolvedValueOnce({
				status: 200,
				data: { count: 10, rows: [glossaryMemory("memory-1")] },
				headers: new Headers(),
			});
		const { result } = renderHook(() => useTermMemories("group-1", "term-1", "chapter-1"));

		expect(
			readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
		).not.toHaveBeenCalled();
		act(() => result.current.loadMemories());
		await waitFor(() => expect(result.current.memories.status).toBe("ready"));
		act(() => result.current.loadNextPage());
		await waitFor(() => {
			if (result.current.memories.status !== "ready") return false;
			return result.current.memories.data.start === 11;
		});

		expect(
			readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
		).toHaveBeenLastCalledWith(
			"group-1",
			"term-1",
			{
				skip: TERM_MEMORY_PAGE_SIZE,
				limit: TERM_MEMORY_PAGE_SIZE,
				chapterId: "chapter-1",
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		act(() => result.current.reloadMemoriesAfterDelete());
		await waitFor(() =>
			expect(
				readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
			).toHaveBeenCalledTimes(3),
		);
		expect(
			readMemoriesForTermMemoryGroupsMemoryGroupIdGlossaryTermsTermIdMemoriesGet,
		).toHaveBeenLastCalledWith(
			"group-1",
			"term-1",
			{
				skip: 0,
				limit: TERM_MEMORY_PAGE_SIZE,
				chapterId: "chapter-1",
			},
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);
	});

	it("owns glossary memory draft transitions and preserves preselected terms on reset", () => {
		const { result } = renderHook(() => useGlossaryMemoryForm([termOne]));

		expect(result.current.selectedTermIds).toEqual([termOne.termId]);
		act(() => {
			result.current.setMemoryContent("Lin Fan is an inner disciple.");
			result.current.setMemoryType(MemoryType.rel);
			result.current.setScope(Scope.persist);
			result.current.setTermSelected(termTwo, true);
			result.current.preSend();
		});
		expect(result.current.formStatus).toEqual({ status: "submitting" });
		expect(result.current.selectedTermIds).toEqual([termOne.termId, termTwo.termId]);

		act(() => result.current.onSendError("Could not create memory."));
		expect(result.current.formStatus).toEqual({
			status: "error",
			message: "Could not create memory.",
		});
		act(() => result.current.resetForm());
		expect(result.current.memoryContent).toBe("");
		expect(result.current.memoryType).toBe(MemoryType.fact);
		expect(result.current.scope).toBeNull();
		expect(result.current.selectedTerms).toEqual([termOne]);
		expect(result.current.formStatus).toEqual({ status: "idle" });
	});
});
