import type { RefObject } from "react";
import { Effect } from "effect";
import { UnknownError } from "effect/Cause";
import { readAutolabelByIdAutoLabelsAutoLabelIdGet } from "@/api/endpoints/default/default";
import type { LabelBase } from "@/api/models";
import type { SelectedAutoLabelRun } from "@/autolabels/runs/autoLabelRunsState";
import type { CCProvId, CProvId } from "../controller/types/idTypes";
import type { NovelGetters, TriggerEvent } from "../controller/types/controllerTypes";
import type { EditorData } from "../hooks/useEditorState";
import type { useAutoLabelPreview } from "../hooks/useAutoLabelPreview";
import { labelsToUtf16 } from "../utils/textPositions";

export type AutoLabelManager = {
	setSelectedRun(selection: SelectedAutoLabelRun): void;
	setPreviewEnabled(enabled: boolean): void;
	handleControllerEvent(getters: NovelGetters, event: TriggerEvent): Effect.Effect<void>;
};

type InFlightPreviewRequest = {
	readonly autoLabelId: string;
	readonly chapterId: CProvId;
	readonly chapterContentServId: string;
	readonly abort: AbortController;
};

export function createAutoLabelManager({
	controllerGetters,
	autoLabelPreview,
	dataRef,
}: {
	controllerGetters: NovelGetters;
	autoLabelPreview: ReturnType<typeof useAutoLabelPreview>;
	dataRef: RefObject<EditorData>;
}): AutoLabelManager {
	const invalidatedContentIds = new Map<CProvId, CCProvId>();
	const previewDataCache = new Map<string, readonly LabelBase[]>();
	let selectedRun: SelectedAutoLabelRun = { runId: null };
	let inFlightPreview: InFlightPreviewRequest | null = null;

	function currentChapterId(): CProvId | null {
		const data = dataRef.current;
		if (data.empty || data.loading) return null;
		return data.chapterId;
	}

	function cancelInFlightPreview(): void {
		if (inFlightPreview !== null) {
			inFlightPreview.abort.abort();
			inFlightPreview = null;
		}
	}

	async function loadPreviewLabels(request: InFlightPreviewRequest): Promise<void> {
		try {
			const resp = await readAutolabelByIdAutoLabelsAutoLabelIdGet(request.autoLabelId, {
				signal: request.abort.signal,
			});
			if (request.abort.signal.aborted || inFlightPreview !== request) return;
			inFlightPreview = null;
			if (resp.status !== 200) {
				autoLabelPreview.setPreview(null);
				return;
			}
			const labels = resp.data.autoLabelData ? [...resp.data.autoLabelData] : [];
			previewDataCache.set(request.autoLabelId, labels);
			await Effect.runPromise(syncPreview());
		} catch (err) {
			if (request.abort.signal.aborted || inFlightPreview !== request) return;
			inFlightPreview = null;
			autoLabelPreview.setPreview(null);
			console.error("Failed to load autolabel preview data:", err);
		}
	}

	function syncPreview(): Effect.Effect<void> {
		return Effect.gen(function* () {
			if (!autoLabelPreview.enabledRef.current) {
				cancelInFlightPreview();
				return;
			}

			const chapterId = currentChapterId();
			if (selectedRun.runId === null || chapterId === null) {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				return;
			}

			if (selectedRun.status === "loading") {
				cancelInFlightPreview();
				autoLabelPreview.setLoading(true);
				return;
			}

			if (selectedRun.status !== "ready") {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				return;
			}

			const chapterSlot = yield* controllerGetters
				.chapterGetterSlot(chapterId)
				.pipe(Effect.mapError((err) => new UnknownError({ orig: err })));
			if (chapterSlot.status !== "ready" || !chapterSlot.data.chapterGetters.isTextSynced()) {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				return;
			}

			const chapterContentId = yield* chapterSlot.data.chapterGetters
				.chapterContentId()
				.pipe(Effect.mapError((err) => new UnknownError({ orig: err })));
			const invalidatedContentId = invalidatedContentIds.get(chapterId);
			if (invalidatedContentId === chapterContentId) {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				return;
			}
			if (invalidatedContentId !== undefined) invalidatedContentIds.delete(chapterId);

			const chapterServId = yield* controllerGetters.chapterServerId(chapterId);
			const ccServId = yield* controllerGetters.chapterContentServerId(chapterId);
			if (chapterServId === null || ccServId === null) {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				return;
			}

			const matching = selectedRun.autolabels.find(
				(al) =>
					al.chapterId === chapterServId &&
					al.autoLabelMeta.chapterContentId === ccServId &&
					al.autoLabelMeta.autoLabelStatus === "done",
			);
			if (!matching) {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				return;
			}

			const autoLabelId = matching.autoLabelMeta.autoLabelId;
			const cached = previewDataCache.get(autoLabelId);
			if (cached !== undefined) {
				cancelInFlightPreview();
				const text = yield* chapterSlot.data.chapterGetters.text();
				autoLabelPreview.setPreview(labelsToUtf16(text, cached));
				return;
			}

			if (
				inFlightPreview !== null &&
				inFlightPreview.autoLabelId === autoLabelId &&
				inFlightPreview.chapterId === chapterId &&
				inFlightPreview.chapterContentServId === ccServId
			) {
				return;
			}

			cancelInFlightPreview();
			const request: InFlightPreviewRequest = {
				autoLabelId,
				chapterId,
				chapterContentServId: ccServId,
				abort: new AbortController(),
			};
			inFlightPreview = request;
			autoLabelPreview.setLoading(true);
			void loadPreviewLabels(request);
		}).pipe(
			Effect.catch((err) => {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				console.error("Failed to synchronize autolabel preview:", err);
				return Effect.succeed(void 0);
			}),
		);
	}

	function syncPreviewNow(): void {
		void Effect.runPromise(syncPreview()).catch((err) => {
			console.error("Failed to run autolabel preview synchronization:", err);
		});
	}

	function handleControllerEvent(
		getters: NovelGetters,
		event: TriggerEvent,
	): Effect.Effect<void> {
		return Effect.gen(function* () {
			switch (event.eventType) {
				case "chapterOpened": {
					const chapterServId = yield* getters.chapterServerId(event.chapterId);
					if (chapterServId !== null) {
						const chapterSlot = yield* getters
							.chapterGetterSlot(event.chapterId)
							.pipe(Effect.mapError((err) => new UnknownError({ orig: err })));
						if (chapterSlot.status === "ready") {
							const chapterContentId =
								yield* chapterSlot.data.chapterGetters.chapterContentId();
							const invalidated =
								invalidatedContentIds.get(event.chapterId) === chapterContentId;
							if (!invalidated) invalidatedContentIds.delete(event.chapterId);
							const ccServId =
								!invalidated && chapterSlot.data.chapterGetters.isTextSynced()
									? yield* getters.chapterContentServerId(event.chapterId)
									: null;
							autoLabelPreview.setOpenChapterContentId(chapterServId, ccServId);
						}
					}
					if (event.flags.forEditor) {
						yield* syncPreview();
					}
					break;
				}

				case "chapterClosed": {
					const chapterServId = yield* getters.chapterServerId(event.chapterId);
					if (chapterServId !== null) {
						autoLabelPreview.removeOpenChapterContentId(chapterServId);
					}
					invalidatedContentIds.delete(event.chapterId);
					if (event.chapterId === currentChapterId()) {
						cancelInFlightPreview();
						autoLabelPreview.setPreview(null);
					}
					break;
				}

				case "textChanged": {
					const chapterServId = yield* getters.chapterServerId(event.chapterId);
					if (chapterServId !== null) {
						autoLabelPreview.setOpenChapterContentId(chapterServId, null);
					}
					const chapterSlot = yield* getters
						.chapterGetterSlot(event.chapterId)
						.pipe(Effect.mapError((err) => new UnknownError({ orig: err })));
					if (chapterSlot.status === "ready") {
						invalidatedContentIds.set(
							event.chapterId,
							yield* chapterSlot.data.chapterGetters.chapterContentId(),
						);
					}
					if (event.chapterId === currentChapterId()) {
						cancelInFlightPreview();
						autoLabelPreview.setPreview(null);
					}
					break;
				}
			}
		}).pipe(
			Effect.catch((err) => {
				cancelInFlightPreview();
				autoLabelPreview.setPreview(null);
				console.error("Error in autolabel manager:", err);
				return Effect.succeed(void 0);
			}),
		);
	}

	return {
		setSelectedRun(selection) {
			selectedRun = selection;
			syncPreviewNow();
		},
		setPreviewEnabled(enabled) {
			if (!enabled) cancelInFlightPreview();
			autoLabelPreview.setEnabled(enabled);
			if (enabled) syncPreviewNow();
		},
		handleControllerEvent,
	};
}
