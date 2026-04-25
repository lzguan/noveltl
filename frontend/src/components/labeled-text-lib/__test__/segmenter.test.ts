import { describe, expect, it } from "vitest";

import {
    makeBasicSegmenter,
    makeFullReducingSegmenter,
    makeReducingSegmenter,
} from "../core/segmenters";
import type { StyledLabel } from "../core/types";

type TestStyle = {
    name: string;
};

type TestLabel = StyledLabel<TestStyle>;

function makeLabel(start: number, end: number, name: string): TestLabel {
    return {
        interval: { start, end },
        style: { name },
    };
}

describe("BasicSegmenter", () => {
    it("returns the full text as one unlabeled segment when there are no labels", () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>();

        expect(segmenter("abcdef", [])).toEqual([
            {
                start: 0,
                text: "abcdef",
                labels: [],
            },
        ]);
    });

    it("partitions text into prefix, labeled segment, gap, labeled segment, and suffix", () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>();
        const labels = [
            makeLabel(1, 3, "first"),
            makeLabel(4, 6, "second"),
        ];

        expect(segmenter("abcdefg", labels)).toEqual([
            {
                start: 0,
                text: "a",
                labels: [],
            },
            {
                start: 1,
                text: "bc",
                labels: [
                    {
                        range: { start: 0, end: 2 },
                        style: { name: "first" },
                    },
                ],
            },
            {
                start: 3,
                text: "d",
                labels: [],
            },
            {
                start: 4,
                text: "ef",
                labels: [
                    {
                        range: { start: 0, end: 2 },
                        style: { name: "second" },
                    },
                ],
            },
            {
                start: 6,
                text: "g",
                labels: [],
            },
        ]);
    });

    it("projects overlapping labels into one segment using relative coordinates", () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>();
        const labels = [
            makeLabel(1, 4, "outer"),
            makeLabel(3, 5, "inner"),
        ];

        expect(segmenter("abcdef", labels)).toEqual([
            {
                start: 0,
                text: "a",
                labels: [],
            },
            {
                start: 1,
                text: "bcde",
                labels: [
                    {
                        range: { start: 0, end: 3 },
                        style: { name: "outer" },
                    },
                    {
                        range: { start: 2, end: 4 },
                        style: { name: "inner" },
                    },
                ],
            },
            {
                start: 5,
                text: "f",
                labels: [],
            },
        ]);
    });

    it("treats touching labels as separate segments when gap is zero", () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>(0);
        const labels = [
            makeLabel(0, 2, "left"),
            makeLabel(2, 4, "right"),
        ];

        expect(segmenter("abcd", labels)).toEqual([
            {
                start: 0,
                text: "ab",
                labels: [
                    {
                        range: { start: 0, end: 2 },
                        style: { name: "left" },
                    },
                ],
            },
            {
                start: 2,
                text: "cd",
                labels: [
                    {
                        range: { start: 0, end: 2 },
                        style: { name: "right" },
                    },
                ],
            },
        ]);
    });

    it("merges touching labels when gap is one", () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>(1);
        const labels = [
            makeLabel(0, 2, "left"),
            makeLabel(2, 4, "right"),
        ];

        expect(segmenter("abcd", labels)).toEqual([
            {
                start: 0,
                text: "abcd",
                labels: [
                    {
                        range: { start: 0, end: 2 },
                        style: { name: "left" },
                    },
                    {
                        range: { start: 2, end: 4 },
                        style: { name: "right" },
                    },
                ],
            },
        ]);
    });
});

describe("ReducingSegmenter", () => {
    it("splits an overlapping segment into a partition with reduced styles", () => {
        const reducer = (styles: TestStyle[]): TestStyle => ({
            name: styles.map((style) => style.name).join("+"),
        });
        const segmenter = makeReducingSegmenter<TestStyle, TestLabel>(reducer, makeBasicSegmenter<TestStyle, TestLabel>());
        const labels = [
            makeLabel(1, 4, "outer"),
            makeLabel(3, 5, "inner"),
        ];

        expect(segmenter("abcdef", labels)).toEqual([
            {
                start: 0,
                text: "a",
                labels: [
                    {
                        range: { start: 0, end: 1 },
                        style: { name: "" },
                    },
                ],
            },
            {
                start: 1,
                text: "bcde",
                labels: [
                    {
                        range: { start: 0, end: 2 },
                        style: { name: "outer" },
                    },
                    {
                        range: { start: 2, end: 3 },
                        style: { name: "outer+inner" },
                    },
                    {
                        range: { start: 3, end: 4 },
                        style: { name: "inner" },
                    },
                ],
            },
            {
                start: 5,
                text: "f",
                labels: [
                    {
                        range: { start: 0, end: 1 },
                        style: { name: "" },
                    },
                ],
            },
        ]);
    });
});

describe("FullReducingSegmenter", () => {
    it("partitions the full text and preserves unlabeled regions as empty segments", () => {
        const reducer = (styles: TestStyle[]): TestStyle => ({
            name: styles.map((style) => style.name).join("+"),
        });
        const segmenter = makeFullReducingSegmenter<TestStyle, TestLabel>(reducer);
        const labels = [
            makeLabel(1, 4, "outer"),
            makeLabel(3, 5, "inner"),
        ];

        expect(segmenter("abcdef", labels)).toEqual([
            {
                start: 0,
                text: "a",
                labels: [],
            },
            {
                start: 1,
                text: "bc",
                labels: [
                    {
                        range: { start: 0, end: 2 },
                        style: { name: "outer" },
                    },
                ],
            },
            {
                start: 3,
                text: "d",
                labels: [
                    {
                        range: { start: 0, end: 1 },
                        style: { name: "outer+inner" },
                    },
                ],
            },
            {
                start: 4,
                text: "e",
                labels: [
                    {
                        range: { start: 0, end: 1 },
                        style: { name: "inner" },
                    },
                ],
            },
            {
                start: 5,
                text: "f",
                labels: [],
            },
        ]);
    });
});
