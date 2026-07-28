import { afterEach, describe, expect, it, vi } from "vitest";
import { generateRequestKey } from "../types/requestTypes";

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

	it("explains the HTTPS requirement when randomUUID is unavailable", () => {
		vi.stubGlobal("crypto", {});

		expect(() => generateRequestKey()).toThrow(
			"Secure request key generation is unavailable. Open the editor over HTTPS or localhost.",
		);
	});
});
