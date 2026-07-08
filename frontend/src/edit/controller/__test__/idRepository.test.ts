import { describe, expect, it } from "vitest";
import { Effect } from "effect";
import { buildIdRepository } from "../idRepository";
import { CServId, CCServId, LGServId, LDServId } from "../types/idTypes";

const UUID1 = "00000000-0000-0000-0000-000000000001";
const UUID2 = "00000000-0000-0000-0000-000000000002";
const UUID3 = "00000000-0000-0000-0000-000000000003";

describe("newIdAndBindId", () => {
	it("returns the same prov ID for the same server ID (idempotent)", () => {
		const repo = buildIdRepository();
		const first = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID1) }),
		);
		const second = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID1) }),
		);
		expect(second).toBe(first);
	});

	it("returns different prov IDs for different server IDs", () => {
		const repo = buildIdRepository();
		const v1 = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID1) }),
		);
		const v2 = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID2) }),
		);
		expect(v2).not.toBe(v1);
	});

	it("creates new prov ID for new server version without affecting old version binding", () => {
		const repo = buildIdRepository();

		const v1 = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID1) }),
		);
		const v2 = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID2) }),
		);

		expect(Effect.runSync(repo.getServerId({ kind: "chapterContent", provId: v1 }))).toEqual(
			CCServId(UUID1),
		);
		expect(Effect.runSync(repo.getServerId({ kind: "chapterContent", provId: v2 }))).toEqual(
			CCServId(UUID2),
		);
	});

	it("supports all identifiable kinds", () => {
		const repo = buildIdRepository();

		const ch = Effect.runSync(repo.newIdAndBindId({ kind: "chapter", servId: CServId(UUID1) }));
		const cc = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID2) }),
		);
		const lg = Effect.runSync(
			repo.newIdAndBindId({ kind: "labelGroup", servId: LGServId(UUID3) }),
		);
		const ld = Effect.runSync(
			repo.newIdAndBindId({ kind: "labelData", servId: LDServId(UUID1) }),
		);

		expect(Effect.runSync(repo.queryProvId({ kind: "chapter", servId: CServId(UUID1) }))).toBe(
			ch,
		);
		expect(
			Effect.runSync(repo.queryProvId({ kind: "chapterContent", servId: CCServId(UUID2) })),
		).toBe(cc);
		expect(
			Effect.runSync(repo.queryProvId({ kind: "labelGroup", servId: LGServId(UUID3) })),
		).toBe(lg);
		expect(
			Effect.runSync(repo.queryProvId({ kind: "labelData", servId: LDServId(UUID1) })),
		).toBe(ld);
	});
});

describe("multi-version content lifecycle", () => {
	it("chapter content versions coexist in revMap", () => {
		const repo = buildIdRepository();

		const v1 = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID1) }),
		);
		const v2 = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID2) }),
		);
		const v3 = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID3) }),
		);

		expect(
			Effect.runSync(repo.queryProvId({ kind: "chapterContent", servId: CCServId(UUID1) })),
		).toBe(v1);
		expect(
			Effect.runSync(repo.queryProvId({ kind: "chapterContent", servId: CCServId(UUID2) })),
		).toBe(v2);
		expect(
			Effect.runSync(repo.queryProvId({ kind: "chapterContent", servId: CCServId(UUID3) })),
		).toBe(v3);

		expect(v2).not.toBe(v1);
		expect(v3).not.toBe(v1);
		expect(v3).not.toBe(v2);
	});

	it("queryProvId returns null for unmapped server ID", () => {
		const repo = buildIdRepository();
		expect(
			Effect.runSync(repo.queryProvId({ kind: "chapterContent", servId: CCServId(UUID1) })),
		).toBeNull();
	});
});

describe("bindServerId", () => {
	it("binds a newId-created prov ID to a server ID", () => {
		const repo = buildIdRepository();
		const provId = repo.newId("chapterContent");

		Effect.runSync(
			repo.bindServerId({
				kind: "chapterContent",
				provId,
				servId: CCServId(UUID1),
			}),
		);

		expect(
			Effect.runSync(repo.queryProvId({ kind: "chapterContent", servId: CCServId(UUID1) })),
		).toBe(provId);
	});

	it("rejects rebinding an already-bound prov ID", () => {
		const repo = buildIdRepository();
		const provId = Effect.runSync(
			repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID1) }),
		);

		const result = Effect.runSyncExit(
			repo.bindServerId({
				kind: "chapterContent",
				provId,
				servId: CCServId(UUID2),
			}),
		);
		expect(result._tag).toBe("Failure");
	});

	it("rejects binding a server ID already mapped to another prov ID", () => {
		const repo = buildIdRepository();
		Effect.runSync(repo.newIdAndBindId({ kind: "chapterContent", servId: CCServId(UUID1) }));

		const provId = repo.newId("chapterContent");
		const result = Effect.runSyncExit(
			repo.bindServerId({
				kind: "chapterContent",
				provId,
				servId: CCServId(UUID1),
			}),
		);
		expect(result._tag).toBe("Failure");
	});
});

describe("label data versioning", () => {
	it("multiple label data versions coexist", () => {
		const repo = buildIdRepository();

		const ld1 = Effect.runSync(
			repo.newIdAndBindId({ kind: "labelData", servId: LDServId(UUID1) }),
		);
		const ld2 = Effect.runSync(
			repo.newIdAndBindId({ kind: "labelData", servId: LDServId(UUID2) }),
		);

		expect(Effect.runSync(repo.getServerId({ kind: "labelData", provId: ld1 }))).toEqual(
			LDServId(UUID1),
		);
		expect(Effect.runSync(repo.getServerId({ kind: "labelData", provId: ld2 }))).toEqual(
			LDServId(UUID2),
		);
	});
});
