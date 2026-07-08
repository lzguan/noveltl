import { describe, expect, it } from "vitest";
import { Effect } from "effect";
import { DoNothingParamsValue } from "@/api/models";
import { buildAutolabelDataManager } from "../autolabelDataManager";
import { buildIdRepository } from "../idRepository";
import { NotFoundException } from "../types/errors";
import { CProvId } from "../types/idTypes";
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

function buildManager() {
	return buildAutolabelDataManager(
		NOVEL_ID,
		() => Effect.succeed(void 0),
		buildIdRepository(),
		{
			chapterIds: () => Effect.succeed([]),
			chapter: (_chId: CProvId) => Effect.fail(new NotFoundException()),
		},
		[run],
	);
}

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
		Effect.runSync(reloadRequests[0].postSend([autoLabel]));

		expect(reloadRequests[1].reservationRequest.skip()).toBe(true);

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
		const oldAutoLabelId =
			initialSlot.data.autolabels[0].meta.autoLabel.autoLabelMeta.autoLabelId;

		const reloadRequests = Effect.runSync(manager.reloadAutoLabelRun(runId));
		Effect.runSync(reloadRequests[0].postSend([]));

		expect(reloadRequests[1].reservationRequest.skip()).toBe(false);
		expect(reloadRequests[1].reservationRequest.reserveList().autoLabel).toEqual([
			{
				id: oldAutoLabelId,
				kind: "autoLabel",
				desiredState: "detaching",
			},
		]);
	});
});
