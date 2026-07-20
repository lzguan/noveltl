import { afterEach, describe, expect, it, vi } from "vitest";
import { Effect } from "effect";
import { IdempotentCallable } from "../types/helperTypes";
import { generateRequestKey, regenerateKey } from "../types/requestTypes";

describe("request key generation", () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it("generates branded request keys with crypto.randomUUID", () => {
		const randomUUID = vi.fn(() => "00000000-0000-4000-8000-000000000001");
		vi.stubGlobal("crypto", { randomUUID });

		expect(generateRequestKey()).toBe("00000000-0000-4000-8000-000000000001");
		expect(randomUUID).toHaveBeenCalledOnce();
	});

	it("regenerates request keys through the shared generator", () => {
		vi.stubGlobal("crypto", {
			randomUUID: vi.fn(() => "00000000-0000-4000-8000-000000000002"),
		});

		expect(
			regenerateKey({
				active: true,
				variant: "textOp",
				retries: 1,
				reservationRequest: {
					reserveList: IdempotentCallable(() => ({
						autoLabel: [],
						autoLabelRun: [],
						chapter: [],
						chapterContent: [],
						label: [],
						labelData: [],
						labelGroup: [],
					})),
					skip: () => false,
					wait: () => Effect.succeed(false),
				},
				onFailure: () => Effect.succeed(void 0),
				onFatalError: () => Effect.succeed(void 0),
			}).requestKey,
		).toBe("00000000-0000-4000-8000-000000000002");
	});

	it("explains the HTTPS requirement when randomUUID is unavailable", () => {
		vi.stubGlobal("crypto", {});

		expect(() => generateRequestKey()).toThrow(
			"Secure request key generation is unavailable. Open the editor over HTTPS or localhost.",
		);
	});
});
