import { describe, expect, it } from "vitest";

import {
	averageColors,
	blendColors,
	blue,
	fromHex,
	green,
	red,
	rgb,
	toHex,
} from "../builtin/colors";

describe("colors", () => {
	it("packs and unpacks rgb channels", () => {
		const color = rgb(12, 34, 56);

		expect(red(color)).toBe(12);
		expect(green(color)).toBe(34);
		expect(blue(color)).toBe(56);
	});

	it("clamps and rounds channel values", () => {
		const color = rgb(-3, 20.6, 999);

		expect(red(color)).toBe(0);
		expect(green(color)).toBe(21);
		expect(blue(color)).toBe(255);
	});

	it("converts packed colors to css hex", () => {
		expect(toHex(rgb(255, 136, 0))).toBe("#ff8800");
	});

	it("parses 3-digit and 6-digit hex colors", () => {
		expect(fromHex("#f80")).toBe(rgb(255, 136, 0));
		expect(fromHex("#ff8800")).toBe(rgb(255, 136, 0));
	});

	it("averages colors channel-by-channel", () => {
		expect(averageColors([rgb(255, 0, 0), rgb(0, 255, 0), rgb(0, 0, 255)])).toBe(
			rgb(85, 85, 85),
		);
	});

	it("blends colors channel-by-channel", () => {
		expect(blendColors(rgb(255, 0, 0), rgb(0, 0, 255), 0.5)).toBe(rgb(128, 0, 128));
		expect(blendColors(rgb(255, 0, 0), rgb(0, 0, 255), 0)).toBe(rgb(255, 0, 0));
		expect(blendColors(rgb(255, 0, 0), rgb(0, 0, 255), 1)).toBe(rgb(0, 0, 255));
	});
});
