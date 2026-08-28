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

	it("generates a UUID v4 with getRandomValues when randomUUID is unavailable", () => {
		const getRandomValues = vi.fn((bytes: Uint8Array) => {
			bytes.set(Array.from({ length: 16 }, (_, index) => index));
			return bytes;
		});
		vi.stubGlobal("crypto", { getRandomValues });

		expect(generateRequestKey()).toBe("00010203-0405-4607-8809-0a0b0c0d0e0f");
		expect(getRandomValues).toHaveBeenCalledOnce();
	});

	it("explains when UUID generation is unavailable", () => {
		vi.stubGlobal("crypto", {});

		expect(() => generateRequestKey()).toThrow(
			"UUID generation is unavailable in this browser.",
		);
	});
});
