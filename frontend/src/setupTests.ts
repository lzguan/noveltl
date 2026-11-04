import "@testing-library/jest-dom/vitest";
import type {} from "vitest/jsdom";

// Node 26 exposes an unavailable localStorage global without a backing file.
// Use jsdom's browser storage for the browser code exercised by these tests.
// Files marked `@vitest-environment node` have no jsdom and no browser storage.
if (typeof jsdom !== "undefined") {
	Object.defineProperty(globalThis, "localStorage", {
		configurable: true,
		value: jsdom.window.localStorage,
	});
}
