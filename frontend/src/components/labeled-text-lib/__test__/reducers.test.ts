import { describe, expect, it } from "vitest";

import { rgb } from "../builtin/colors";
import {
	makeBoldStyleReducer,
	makeColorStyleAverageReducer,
	makeUnderlineStyleReducer,
	productReducer,
	type BoldStyle,
	type ColorStyle,
	type ProductStyle,
	type UnderlineStyle,
} from "../builtin/reducers";

describe("builtin reducers", () => {
	it("averages ColorStyle values channel-by-channel", () => {
		const reducer = makeColorStyleAverageReducer(rgb(0, 0, 0));
		const styles: ColorStyle[] = [{ color: rgb(255, 0, 0) }, { color: rgb(0, 0, 255) }];

		expect(reducer(styles)).toEqual({
			color: rgb(128, 0, 128),
		} satisfies ColorStyle);
	});

	it("returns the default color for an empty ColorStyle list", () => {
		const reducer = makeColorStyleAverageReducer(rgb(12, 34, 56));

		expect(reducer([])).toEqual({
			color: rgb(12, 34, 56),
		} satisfies ColorStyle);
	});

	it("reduces UnderlineStyle with boolean or semantics", () => {
		const reducer = makeUnderlineStyleReducer();
		const styles: UnderlineStyle[] = [
			{ underline: false },
			{ underline: true },
			{ underline: false },
		];

		expect(reducer(styles)).toEqual({
			underline: true,
		} satisfies UnderlineStyle);
	});

	it("returns false for an empty UnderlineStyle list by default", () => {
		const reducer = makeUnderlineStyleReducer();

		expect(reducer([])).toEqual({
			underline: false,
		} satisfies UnderlineStyle);
	});

	it("reduces BoldStyle with boolean or semantics", () => {
		const reducer = makeBoldStyleReducer();
		const styles: BoldStyle[] = [{ bold: false }, { bold: true }, { bold: false }];

		expect(reducer(styles)).toEqual({
			bold: true,
		} satisfies BoldStyle);
	});

	it("returns false for an empty BoldStyle list by default", () => {
		const reducer = makeBoldStyleReducer();

		expect(reducer([])).toEqual({
			bold: false,
		} satisfies BoldStyle);
	});

	it("combines reducers coordinatewise with productReducer", () => {
		type CombinedStyle = ProductStyle<[ColorStyle, UnderlineStyle, BoldStyle]>;

		const reducer = productReducer(
			makeColorStyleAverageReducer(rgb(0, 0, 0)),
			makeUnderlineStyleReducer(),
			makeBoldStyleReducer(),
		);
		const styles: CombinedStyle[] = [
			[{ color: rgb(255, 0, 0) }, { underline: false }, { bold: false }],
			[{ color: rgb(0, 255, 0) }, { underline: true }, { bold: false }],
			[{ color: rgb(0, 0, 255) }, { underline: false }, { bold: true }],
		];

		expect(reducer(styles)).toEqual([
			{ color: rgb(85, 85, 85) },
			{ underline: true },
			{ bold: true },
		] satisfies CombinedStyle);
	});

	it("uses defaults coordinatewise when productReducer sees an empty list", () => {
		type CombinedStyle = ProductStyle<[ColorStyle, UnderlineStyle, BoldStyle]>;

		const reducer = productReducer(
			makeColorStyleAverageReducer(rgb(10, 20, 30)),
			makeUnderlineStyleReducer(),
			makeBoldStyleReducer(),
		);

		expect(reducer([])).toEqual([
			{ color: rgb(10, 20, 30) },
			{ underline: false },
			{ bold: false },
		] satisfies CombinedStyle);
	});
});
