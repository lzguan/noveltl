import type { LabelPromotionJob } from "@/api/models";
import { applyPoll, EMPTY_STATE, MAX_TRACKED_PROMOTIONS } from "./promotionJobsState";

function job(promotionId: string, status: LabelPromotionJob["status"], minute: number) {
	const at = `2026-11-22T10:${String(minute).padStart(2, "0")}:00Z`;
	return {
		promotionId,
		runId: "run",
		labelGroupId: "group",
		skipExistingLabels: true,
		status,
		message: null,
		counts: { total: 1, done: 0, failed: 0, pending: 1 },
		createdAt: at,
		updatedAt: at,
	};
}

test("a poll moves finished jobs ahead of older ones and evicts the oldest finished", () => {
	const finished = Array.from({ length: MAX_TRACKED_PROMOTIONS - 1 }, (_, i) =>
		job(`old-${i}`, "done", i),
	);
	const previous = { ...EMPTY_STATE, active: [job("a", "processing", 20)], finished };

	const { state, newlyFinished } = applyPoll(previous, new Set(["a", "b"]), [
		job("a", "done", 30),
		job("b", "pending", 31),
	]);

	expect(newlyFinished.map((j) => j.promotionId)).toEqual(["a"]);
	expect(state.active.map((j) => j.promotionId)).toEqual(["b"]);
	expect(state.finished.map((j) => j.promotionId)).toEqual([
		"a",
		...finished
			.map((j) => j.promotionId)
			.reverse()
			.slice(0, MAX_TRACKED_PROMOTIONS - 2),
	]);
});

test("a poll keeps jobs it did not ask about and drops requested ones that vanished", () => {
	const previous = {
		...EMPTY_STATE,
		active: [job("kept", "processing", 1), job("gone", "processing", 2)],
	};

	const { state } = applyPoll(previous, new Set(["gone"]), []);

	expect(state.active.map((j) => j.promotionId)).toEqual(["kept"]);
});
