import { act, renderHook, waitFor } from "@testing-library/react";
import { readAutolabelByIdAutoLabelsAutoLabelIdGet } from "@/api/endpoints/default/default";
import type { AutoLabelMetaWithCid, LabelBase } from "@/api/models";
import type { SelectedAutoLabelRun } from "@/autolabels/runs/autoLabelRunsState";
import { type AutoLabelPreviewTarget, useAutoLabelPreview } from "./useAutoLabelPreview";

vi.mock("@/api/endpoints/default/default", () => ({
	readAutolabelByIdAutoLabelsAutoLabelIdGet: vi.fn(),
}));

const mockedReadAutolabel = vi.mocked(readAutolabelByIdAutoLabelsAutoLabelIdGet);

const CHAPTER_ID = "chapter-1";
const CONTENT_ID = "content-1";
const AUTOLABEL_ID = "al-1";

function makeAutolabel(
	overrides: Partial<AutoLabelMetaWithCid["autoLabelMeta"]> = {},
	chapterId = CHAPTER_ID,
): AutoLabelMetaWithCid {
	return {
		chapterId,
		autoLabelMeta: {
			autoLabelId: AUTOLABEL_ID,
			chapterContentId: CONTENT_ID,
			autoLabelStatus: "done",
			autoLabelMessage: null,
			runId: "run-1",
			...overrides,
		},
	};
}

function makeReadyRun(
	autolabels: readonly AutoLabelMetaWithCid[] = [makeAutolabel()],
): SelectedAutoLabelRun {
	return {
		runId: "run-1",
		status: "ready",
		autolabels,
	};
}

function makeTarget(overrides: Partial<AutoLabelPreviewTarget> = {}): AutoLabelPreviewTarget {
	return {
		chapterId: CHAPTER_ID,
		chapterContentId: CONTENT_ID,
		text: "😀Alice",
		...overrides,
	};
}

function makeLabelsResponse(labels: LabelBase[]) {
	return {
		status: 200 as const,
		headers: new Headers(),
		data: {
			...makeAutolabel().autoLabelMeta,
			autoLabelData: labels,
		},
	};
}

describe("useAutoLabelPreview", () => {
	beforeEach(() => {
		mockedReadAutolabel.mockReset();
	});

	it("does not fetch when preview is disabled", () => {
		const { result } = renderHook(() => useAutoLabelPreview(makeReadyRun(), makeTarget()));

		expect(result.current.enabled).toBe(false);
		expect(result.current.loading).toBe(false);
		expect(result.current.preview).toBeNull();
		expect(mockedReadAutolabel).not.toHaveBeenCalled();
	});

	it("fetches matching autolabels, converts codepoint offsets to UTF-16, and caches results", async () => {
		mockedReadAutolabel.mockResolvedValue(
			makeLabelsResponse([
				{
					labelWord: "Alice",
					labelStart: 1,
					labelEnd: 6,
					labelEntityGroup: "name",
					labelScore: 0.9,
					labelDirty: false,
				},
			]),
		);

		type HookProps = {
			selectedRun: SelectedAutoLabelRun;
			target: AutoLabelPreviewTarget | null;
		};
		const initialProps: HookProps = { selectedRun: makeReadyRun(), target: makeTarget() };
		const { result, rerender } = renderHook(
			({ selectedRun, target }: HookProps) => useAutoLabelPreview(selectedRun, target),
			{ initialProps },
		);

		act(() => {
			result.current.setEnabled(true);
		});

		await waitFor(() => {
			expect(result.current.loading).toBe(false);
			expect(result.current.preview).toEqual([
				{
					labelWord: "Alice",
					labelStart: 2,
					labelEnd: 7,
					labelEntityGroup: "name",
					labelScore: 0.9,
					labelDirty: false,
				},
			]);
		});
		expect(mockedReadAutolabel).toHaveBeenCalledTimes(1);

		// Clearing target (e.g. text edited or chapter closed) clears preview immediately.
		rerender({ selectedRun: makeReadyRun(), target: null });
		expect(result.current.preview).toBeNull();
		expect(result.current.loading).toBe(false);

		// Returning to the same chapter reuses the cache without refetching.
		rerender({ selectedRun: makeReadyRun(), target: makeTarget() });
		expect(result.current.preview).toHaveLength(1);
		expect(mockedReadAutolabel).toHaveBeenCalledTimes(1);
	});

	it("shows loading while the selected run metadata is loading", () => {
		const { result } = renderHook(() =>
			useAutoLabelPreview({ runId: "run-1", status: "loading" }, makeTarget()),
		);

		act(() => {
			result.current.setEnabled(true);
		});

		expect(result.current.loading).toBe(true);
		expect(result.current.preview).toBeNull();
		expect(mockedReadAutolabel).not.toHaveBeenCalled();
	});

	it("aborts in-flight preview fetches when target clears or preview is disabled", () => {
		let capturedSignal: AbortSignal | undefined;
		mockedReadAutolabel.mockImplementation(
			(_id, options) =>
				new Promise(() => {
					capturedSignal = options?.signal ?? undefined;
				}),
		);

		type TargetProps = { target: AutoLabelPreviewTarget | null };
		const initialProps: TargetProps = { target: makeTarget() };
		const { result, rerender } = renderHook(
			({ target }: TargetProps) => useAutoLabelPreview(makeReadyRun(), target),
			{ initialProps },
		);

		act(() => {
			result.current.setEnabled(true);
		});
		expect(result.current.loading).toBe(true);
		expect(capturedSignal?.aborted).toBe(false);

		rerender({ target: null });
		expect(capturedSignal?.aborted).toBe(true);
		expect(result.current.loading).toBe(false);
		expect(result.current.preview).toBeNull();
	});

	it("clears loading on failed fetch and retries when preview is re-enabled", async () => {
		const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
		mockedReadAutolabel.mockRejectedValueOnce(new Error("network down"));

		const { result } = renderHook(() => useAutoLabelPreview(makeReadyRun(), makeTarget()));

		act(() => {
			result.current.setEnabled(true);
		});

		await waitFor(() => {
			expect(result.current.loading).toBe(false);
		});
		expect(result.current.preview).toBeNull();
		expect(mockedReadAutolabel).toHaveBeenCalledTimes(1);

		mockedReadAutolabel.mockResolvedValueOnce(
			makeLabelsResponse([
				{
					labelWord: "Alice",
					labelStart: 1,
					labelEnd: 6,
					labelEntityGroup: "name",
					labelScore: 0.9,
					labelDirty: false,
				},
			]),
		);

		act(() => {
			result.current.setEnabled(false);
		});
		act(() => {
			result.current.setEnabled(true);
		});

		await waitFor(() => {
			expect(result.current.preview).toHaveLength(1);
		});
		expect(mockedReadAutolabel).toHaveBeenCalledTimes(2);
		errorSpy.mockRestore();
	});
});
