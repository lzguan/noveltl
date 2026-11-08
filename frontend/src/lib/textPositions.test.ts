// @vitest-environment node

import { describe, expect, it } from "vitest";
import { codePointLength, createTextPositionMap } from "./textPositions";

describe("text positions shared with Python", () => {
	it.each(["", "Alice白玫", "A😀𠮷B", "e\u0301", "👩‍💻"])("maps every boundary in %j", (text) => {
		const positions = createTextPositionMap(text);
		const characters = Array.from(text);
		for (let index = 0; index <= characters.length; index++) {
			const utf16Offset = characters.slice(0, index).join("").length;
			expect(positions.toUtf16(index)).toBe(utf16Offset);
			expect(positions.toCodePoint(utf16Offset)).toBe(index);
		}
		expect(codePointLength(text)).toBe(characters.length);
	});

	it("rejects positions inside a surrogate pair", () => {
		expect(() => createTextPositionMap("A😀B").toCodePoint(2)).toThrow(RangeError);
	});

	it.each([-1, 4, 0.5, NaN, Infinity])("rejects invalid code-point position %s", (position) => {
		expect(() => createTextPositionMap("A😀B").toUtf16(position)).toThrow(RangeError);
	});

	it.each([-1, 5, 0.5, NaN, Infinity])("rejects invalid UTF-16 position %s", (position) => {
		expect(() => createTextPositionMap("A😀B").toCodePoint(position)).toThrow(RangeError);
	});
});
