import { describe, expect, it } from "vitest";
import { Effect } from "effect";
import { DoNothingParamsValue } from "@/api/models";
import { buildAutolabelDataManager } from "../autolabelDataManager";
import { buildIdRepository } from "../idRepository";
import { NotFoundException } from "../types/errors";
import type { TriggerEvent } from "../types/controllerTypes";
import { CProvId, LGProvId } from "../types/idTypes";
import type { AutoLabelMetaWithCidOutput, AutoLabelRunOutput } from "@/api/models";

const NOVEL_ID = "00000000-0000-0000-0000-00000000000a";
const RUN_ID = "00000000-0000-0000-0000-00000000000b";
const AUTOLABEL_ID = "00000000-0000-0000-0000-00000000000c";
const CHAPTER_ID = "00000000-0000-0000-0000-00000000000d";
const CHAPTER_CONTENT_ID = "00000000-0000-0000-0000-00000000000e";

const run: AutoLabelRunOutput = {
	createdAt: "2026-01-01T00:00:00Z",
	modelName: "do_nothing",
	modelParams: DoNothingParamsValue,
	novelId: NOVEL_ID,
	runId: RUN_ID,
	triggeredBy: "00000000-0000-0000-0000-00000000000f",
};

const autoLabel: AutoLabelMetaWithCidOutput = {
	autoLabelMeta: {
		autoLabelId: AUTOLABEL_ID,
		autoLabelLastJobId: null,
		autoLabelMessage: null,
		autoLabelStatus: "done",
		chapterContentId: CHAPTER_CONTENT_ID,
		runId: RUN_ID,
	},
	chapterId: CHAPTER_ID,
};

function buildManager(events: TriggerEvent[] = []) {
	return buildAutolabelDataManager(
		NOVEL_ID,
		(event) =>
			Effect.sync(() => {
				events.push(event);
			}),
		buildIdRepository(),
		{
			chapterIds: () => Effect.succeed([]),
			chapter: (_chId: CProvId) => Effect.fail(new NotFoundException()),
		},
		[run],
	);
}

const LABEL_GROUP_ID = LGProvId("00000000-0000-0000-0000-000000000010");

describe("buildAutolabelDataManager", () => {
	it("does not clean up autolabel IDs that are reused by reload", () => {
		const manager = Effect.runSync(buildManager());
		const runId = Effect.runSync(manager.getters.autoLabelRunIds())[0];
		expect(runId).toBeDefined();

		const initialRequests = Effect.runSync(manager.reloadAutoLabelRun(runId));
		Effect.runSync(initialRequests[0].postSend([autoLabel]));
		const initialSlot = Effect.runSync(manager.getters.autoLabelRunSlot(runId));
		expect(initialSlot.status).toBe("ready");
		if (initialSlot.status !== "ready") return;
		const initialAutoLabelId =
			initialSlot.data.autolabels[0].meta.autoLabel.autoLabelMeta.autoLabelId;

		const reloadRequests = Effect.runSync(manager.reloadAutoLabelRun(runId));
		expect(reloadRequests).toHaveLength(1);
		Effect.runSync(reloadRequests[0].postSend([autoLabel]));

		const slot = Effect.runSync(manager.getters.autoLabelRunSlot(runId));
		expect(slot.status).toBe("ready");
		if (slot.status === "ready") {
			expect(slot.data.autolabels).toHaveLength(1);
			expect(slot.data.autolabels[0].meta.autoLabel.autoLabelMeta.autoLabelId).toBe(
				initialAutoLabelId,
			);
		}
	});

	it("still cleans up old autolabel IDs that are missing after reload", () => {
		const manager = Effect.runSync(buildManager());
		const runId = Effect.runSync(manager.getters.autoLabelRunIds())[0];
		expect(runId).toBeDefined();

		const initialRequests = Effect.runSync(manager.reloadAutoLabelRun(runId));
		Effect.runSync(initialRequests[0].postSend([autoLabel]));
		const initialSlot = Effect.runSync(manager.getters.autoLabelRunSlot(runId));
		expect(initialSlot.status).toBe("ready");
		if (initialSlot.status !== "ready") return;

		const reloadRequests = Effect.runSync(manager.reloadAutoLabelRun(runId));
		expect(reloadRequests).toHaveLength(1);
		Effect.runSync(reloadRequests[0].postSend([]));

		const slot = Effect.runSync(manager.getters.autoLabelRunSlot(runId));
		expect(slot.status).toBe("ready");
		if (slot.status === "ready") {
			expect(slot.data.autolabels).toHaveLength(0);
		}
	});

	it("emits a successful terminal event for promotion results with chapter errors", () => {
		const events: TriggerEvent[] = [];
		const manager = Effect.runSync(buildManager(events));
		const runId = Effect.runSync(manager.getters.autoLabelRunIds())[0];
		expect(runId).toBeDefined();

		const requests = Effect.runSync(manager.promoteAutoLabelRun(runId, LABEL_GROUP_ID, {}));
		expect(requests).toHaveLength(1);
		Effect.runSync(
			requests[0].postSend({
				success: [],
				errors: [[CHAPTER_ID, CHAPTER_CONTENT_ID, "Overlapping labels"]],
			}),
		);

		const finished = events.find(
			(event) => event.eventType === "autoLabelRunPromotionFinished",
		);
		expect(finished).toBeDefined();
		if (finished?.eventType !== "autoLabelRunPromotionFinished") return;
		expect(finished.outcome).toBe("success");
		if (finished.outcome !== "success") return;
		expect(finished.success).toHaveLength(0);
		expect(finished.errors).toHaveLength(1);
		expect(finished.errors[0].error).toBe("Overlapping labels");
	});

	it("emits a failed terminal event when promotion exhausts retries", () => {
		const events: TriggerEvent[] = [];
		const manager = Effect.runSync(buildManager(events));
		const runId = Effect.runSync(manager.getters.autoLabelRunIds())[0];
		expect(runId).toBeDefined();

		const requests = Effect.runSync(manager.promoteAutoLabelRun(runId, LABEL_GROUP_ID, {}));
		Effect.runSync(requests[0].onFailure());

		const finished = events.find(
			(event) => event.eventType === "autoLabelRunPromotionFinished",
		);
		expect(finished).toBeDefined();
		if (finished?.eventType !== "autoLabelRunPromotionFinished") return;
		expect(finished.outcome).toBe("failure");
		if (finished.outcome !== "failure") return;
		expect(finished.error.message).toContain("exhausting request retries");
	});

	it("emits a failed terminal event for a fatal promotion error", () => {
		const events: TriggerEvent[] = [];
		const manager = Effect.runSync(buildManager(events));
		const runId = Effect.runSync(manager.getters.autoLabelRunIds())[0];
		expect(runId).toBeDefined();
		const error = new Error("Fatal promotion error");

		const requests = Effect.runSync(manager.promoteAutoLabelRun(runId, LABEL_GROUP_ID, {}));
		Effect.runSync(requests[0].onFatalError(error));

		const finished = events.find(
			(event) => event.eventType === "autoLabelRunPromotionFinished",
		);
		expect(finished).toBeDefined();
		if (finished?.eventType !== "autoLabelRunPromotionFinished") return;
		expect(finished.outcome).toBe("failure");
		if (finished.outcome !== "failure") return;
		expect(finished.error).toBe(error);
	});
});
