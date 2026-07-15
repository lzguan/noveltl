import { act, renderHook } from "@testing-library/react";
import { Effect } from "effect";
import type { NovelData } from "../controller/novelDataManager";
import { buildNovelController } from "../controller/controller";
import type { NovelUserEvent } from "../controller/types/controllerTypes";
import { IdempotentCallable } from "../controller/types/helperTypes";
import { ALRProvId, LGProvId } from "../controller/types/idTypes";
import { RequestKey, type RequestEvent } from "../controller/types/requestTypes";
import { useAutoLabelPreview } from "../hooks/useAutoLabelPreview";
import { useAutoLabelState } from "../hooks/useAutoLabelState";
import { useEditorState } from "../hooks/useEditorState";
import { useWorkspaceLock } from "../hooks/useWorkspaceLock";
import { createAutoLabelManager } from "./autolabelManager";

const NOVEL_ID = "00000000-0000-0000-0000-000000000001";
const RUN_ID = ALRProvId("00000000-0000-0000-0000-000000000002");
const LABEL_GROUP_ID = LGProvId("00000000-0000-0000-0000-000000000003");

function makeNovelData(): NovelData {
	return {
		novel: {
			novelId: NOVEL_ID,
			novelTitle: "Test Novel",
			novelDescription: null,
			novelAuthor: "Author",
			novelVisibility: 0,
			novelType: "original",
			languageCode: "en",
			sourceWorkId: "00000000-0000-0000-0000-000000000004",
		},
		chapters: [],
		labelGroups: [],
		novelRole: "owner",
		autoLabelRuns: [],
	};
}

function renderManager(onUserEvent?: (event: NovelUserEvent) => void) {
	const controller = Effect.runSync(buildNovelController(makeNovelData()));
	const userEvents: NovelUserEvent[] = [];
	const hooks = renderHook(() => ({
		autoLabels: useAutoLabelState(),
		autoLabelPreview: useAutoLabelPreview(),
		editor: useEditorState(),
		workspace: useWorkspaceLock(),
	}));

	act(() => hooks.result.current.editor.setMode("label"));

	const manager = createAutoLabelManager({
		controllerUserEvent(event) {
			userEvents.push(event);
			onUserEvent?.(event);
		},
		controllerGetters: controller.getters,
		autoLabels: hooks.result.current.autoLabels,
		autoLabelPreview: hooks.result.current.autoLabelPreview,
		dataRef: hooks.result.current.editor.dataRef,
		modeRef: hooks.result.current.editor.modeRef,
		setMode: hooks.result.current.editor.setMode,
		acquireLock: hooks.result.current.workspace.acquireLock,
		releaseLock: hooks.result.current.workspace.releaseLock,
	});

	return { controller, hooks, manager, userEvents };
}

function makePreviewLoadRequest() {
	const emptyReservations = IdempotentCallable(() => ({
		autoLabelRun: [],
		autoLabel: [],
		label: [],
		chapter: [],
		chapterContent: [],
		labelData: [],
		labelGroup: [],
	}));
	const request = {
		cached: false,
		variant: "loadAutoLabelData",
		active: false,
		retries: 3,
		reservationRequest: {
			reserveList: emptyReservations,
			skip: () => false,
			wait: () => Effect.succeed(false),
		},
		onFailure: () => Effect.succeed(void 0),
		onFatalError: () => Effect.succeed(void 0),
		preSend: () => Effect.succeed(void 0),
		send: () => Effect.succeed(undefined),
		postSend: () => Effect.succeed(void 0),
	} satisfies RequestEvent;
	return { ...request, requestKey: RequestKey(crypto.randomUUID()) };
}

describe("createAutoLabelManager promotion lifecycle", () => {
	it("keeps promotion locked when an unrelated data-manager error occurs", () => {
		const { controller, hooks, manager } = renderManager();

		act(() => manager.promote(RUN_ID, LABEL_GROUP_ID, {}));
		expect(hooks.result.current.autoLabels.promoting).toBe(true);
		expect(hooks.result.current.editor.mode).toBe("view");
		expect(hooks.result.current.workspace.workspaceLock).not.toBeNull();

		act(() => {
			Effect.runSync(
				manager.handleControllerEvent(controller.getters, {
					eventType: "errorOccured",
					from: "dataManager",
					error: new Error("Unrelated preview failure"),
				}),
			);
		});

		expect(hooks.result.current.autoLabels.promoting).toBe(true);
		expect(hooks.result.current.editor.mode).toBe("view");
		expect(hooks.result.current.workspace.workspaceLock).not.toBeNull();
	});

	it("keeps promotion locked when a preview request fails", () => {
		const { controller, hooks, manager } = renderManager();

		act(() => manager.promote(RUN_ID, LABEL_GROUP_ID, {}));

		act(() => {
			Effect.runSync(
				manager.handleControllerEvent(controller.getters, {
					eventType: "errorOccured",
					from: "requestManager",
					data: [
						{
							error: new Error("Preview load failed"),
							request: makePreviewLoadRequest(),
						},
					],
				}),
			);
		});

		expect(hooks.result.current.autoLabels.promoting).toBe(true);
		expect(hooks.result.current.editor.mode).toBe("view");
		expect(hooks.result.current.workspace.workspaceLock).not.toBeNull();
	});

	it("releases promotion state when the matching promotion succeeds", () => {
		const { controller, hooks, manager } = renderManager();

		act(() => manager.promote(RUN_ID, LABEL_GROUP_ID, {}));
		act(() => {
			Effect.runSync(
				manager.handleControllerEvent(controller.getters, {
					eventType: "autoLabelRunPromotionFinished",
					runId: RUN_ID,
					outcome: "success",
					labelGroupId: LABEL_GROUP_ID,
					chapterFilter: {},
					success: [],
					errors: [],
				}),
			);
		});

		expect(hooks.result.current.autoLabels.promoting).toBe(false);
		expect(hooks.result.current.editor.mode).toBe("label");
		expect(hooks.result.current.workspace.workspaceLock).toBeNull();
	});

	it("releases promotion state when the matching promotion fails", () => {
		const { controller, hooks, manager } = renderManager();

		act(() => manager.promote(RUN_ID, LABEL_GROUP_ID, {}));
		act(() => {
			Effect.runSync(
				manager.handleControllerEvent(controller.getters, {
					eventType: "autoLabelRunPromotionFinished",
					runId: RUN_ID,
					outcome: "failure",
					error: new Error("Promotion failed"),
				}),
			);
		});

		expect(hooks.result.current.autoLabels.promoting).toBe(false);
		expect(hooks.result.current.editor.mode).toBe("label");
		expect(hooks.result.current.workspace.workspaceLock).toBeNull();
	});

	it("keeps promotion locked for a different run's completion", () => {
		const { controller, hooks, manager } = renderManager();

		act(() => manager.promote(RUN_ID, LABEL_GROUP_ID, {}));
		act(() => {
			Effect.runSync(
				manager.handleControllerEvent(controller.getters, {
					eventType: "autoLabelRunPromotionFinished",
					runId: ALRProvId("00000000-0000-0000-0000-000000000005"),
					outcome: "failure",
					error: new Error("Another promotion failed"),
				}),
			);
		});

		expect(hooks.result.current.autoLabels.promoting).toBe(true);
		expect(hooks.result.current.editor.mode).toBe("view");
		expect(hooks.result.current.workspace.workspaceLock).not.toBeNull();
	});

	it("restores promotion state when dispatch throws synchronously", () => {
		const error = new Error("Dispatch failed");
		const { hooks, manager } = renderManager(() => {
			throw error;
		});

		expect(() => {
			act(() => manager.promote(RUN_ID, LABEL_GROUP_ID, {}));
		}).toThrow(error);

		expect(hooks.result.current.autoLabels.promoting).toBe(false);
		expect(hooks.result.current.editor.mode).toBe("label");
		expect(hooks.result.current.workspace.workspaceLock).toBeNull();
	});
});
