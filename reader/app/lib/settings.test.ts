import { describe, expect, it } from "vitest";
import {
	applySettingsOp,
	DEFAULT_SETTINGS,
	parseSettings,
	safeReturnTo,
	serializeSettings,
} from "./settings";

describe("parseSettings", () => {
	it("returns defaults without a cookie", () => {
		expect(parseSettings(null)).toEqual(DEFAULT_SETTINGS);
		expect(parseSettings("other=1")).toEqual(DEFAULT_SETTINGS);
	});

	it("round-trips serialized settings", () => {
		const settings = { fontSize: 22, lineHeight: 2, theme: "dark" } as const;
		const cookie = serializeSettings(settings).split(";")[0] ?? "";
		expect(parseSettings(`a=b; ${cookie}; c=d`)).toEqual(settings);
	});

	it("falls back per field on invalid values", () => {
		const raw = encodeURIComponent("fontSize=999&lineHeight=abc&theme=dark");
		expect(parseSettings(`reader_settings=${raw}`)).toEqual({
			...DEFAULT_SETTINGS,
			theme: "dark",
		});
		expect(parseSettings("reader_settings=%E0%A4%A")).toEqual(DEFAULT_SETTINGS);
	});
});

describe("applySettingsOp", () => {
	it("steps and clamps font size", () => {
		expect(applySettingsOp(DEFAULT_SETTINGS, "font-larger").fontSize).toBe(20);
		const smallest = { ...DEFAULT_SETTINGS, fontSize: 15 };
		expect(applySettingsOp(smallest, "font-smaller").fontSize).toBe(15);
	});

	it("sets theme", () => {
		expect(applySettingsOp(DEFAULT_SETTINGS, "theme-dark").theme).toBe("dark");
	});
});

describe("safeReturnTo", () => {
	it("only allows same-origin paths", () => {
		expect(safeReturnTo("/novel/x/2?a=1")).toBe("/novel/x/2?a=1");
		expect(safeReturnTo("//evil.example")).toBe("/");
		expect(safeReturnTo("/\\evil.example")).toBe("/");
		expect(safeReturnTo("https://evil.example")).toBe("/");
		expect(safeReturnTo(null)).toBe("/");
	});
});
