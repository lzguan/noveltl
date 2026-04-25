import { describe, expect, it } from "vitest";

import { getUncoveredSubintervals, makeBasicSegmentManager } from "../core/segmentManager";
import type { StyledLabel } from "../core/types";

type TestStyle = {
    name: string;
};

type ManagedTestLabel = StyledLabel<TestStyle> & {
    id: string;
};

function makeLabel(id: string, start: number, end: number, name: string): ManagedTestLabel {
    return {
        id,
        interval: { start, end },
        style: { name },
    };
}

function assertManagerInvariants(manager: ReturnType<typeof makeBasicSegmentManager<TestStyle, ManagedTestLabel>>) {
    const text = manager.getText();
    const segments = manager.getSegments();
    const segmentIds = manager.getSegmentIds();

    expect(segmentIds).toEqual(segments.map((segment) => segment.id));
    expect(segments.map((segment) => segment.text).join("")).toBe(text);

    let cursor = 0;
    for (const segment of segments) {
        expect(segment.start).toBe(cursor);
        expect(segment.text.length).toBeGreaterThan(0);

        for (const label of segment.labels) {
            expect(label.interval.start).toBeGreaterThanOrEqual(0);
            expect(label.interval.end).toBeGreaterThan(label.interval.start);
            expect(label.interval.end).toBeLessThanOrEqual(segment.text.length);
        }

        cursor += segment.text.length;
    }

    expect(cursor).toBe(text.length);
}

function getAbsoluteLabels(manager: ReturnType<typeof makeBasicSegmentManager<TestStyle, ManagedTestLabel>>) {
    return manager
        .getSegments()
        .flatMap((segment) =>
            segment.labels.map((label) => ({
                id: label.id,
                start: segment.start + label.interval.start,
                end: segment.start + label.interval.end,
                name: label.style.name,
            })),
        )
        .sort((left, right) => left.start - right.start || left.id.localeCompare(right.id));
}

describe("getUncoveredSubintervals", () => {
    it("returns the gaps inside the target interval", () => {
        expect(
            getUncoveredSubintervals(
                { start: 0, end: 10 },
                [
                    { start: 1, end: 3 },
                    { start: 2, end: 4 },
                    { start: 7, end: 9 },
                ],
            ),
        ).toEqual([
            { start: 0, end: 1 },
            { start: 4, end: 7 },
            { start: 9, end: 10 },
        ]);
    });

    it("ignores covered intervals that do not intersect the target", () => {
        expect(
            getUncoveredSubintervals(
                { start: 5, end: 12 },
                [
                    { start: 0, end: 2 },
                    { start: 7, end: 9 },
                    { start: 15, end: 18 },
                ],
            ),
        ).toEqual([
            { start: 5, end: 7 },
            { start: 9, end: 12 },
        ]);
    });
});

describe("BasicSegmentManager", () => {
    it("initializes segments from the basic segmenter in text order", () => {
        const manager = makeBasicSegmentManager<TestStyle, ManagedTestLabel>(
            "abcdef",
            [makeLabel("1", 1, 3, "name")],
        );

        expect(manager.getText()).toBe("abcdef");
        expect(manager.getSegments()).toEqual([
            {
                id: "0",
                start: 0,
                text: "a",
                labels: [],
            },
            {
                id: "1",
                start: 1,
                text: "bc",
                labels: [
                    {
                        id: "1",
                        range: { start: 0, end: 2 },
                        style: { name: "name" },
                    },
                ],
            },
            {
                id: "2",
                start: 3,
                text: "def",
                labels: [],
            },
        ]);
        assertManagerInvariants(manager);
        expect(getAbsoluteLabels(manager)).toEqual([
            { id: "1", start: 1, end: 3, name: "name" },
        ]);
    });

    it("inserts text into an unlabeled segment and keeps the manager coherent", () => {
        const manager = makeBasicSegmentManager<TestStyle, ManagedTestLabel>("abef", []);

        manager.insertTextAt(2, "cd");

        expect(manager.getText()).toBe("abcdef");
        assertManagerInvariants(manager);
        expect(getAbsoluteLabels(manager)).toEqual([]);
    });

    it("deletes text from an unlabeled segment and rebuilds the local region", () => {
        const manager = makeBasicSegmentManager<TestStyle, ManagedTestLabel>("abcdef", []);

        manager.deleteTextAt(2, 2);

        expect(manager.getText()).toBe("abef");
        assertManagerInvariants(manager);
        expect(getAbsoluteLabels(manager)).toEqual([]);
    });

    it("preserves invariants across a longer unlabeled editing sequence", () => {
        const manager = makeBasicSegmentManager<TestStyle, ManagedTestLabel>("abcdefghij", []);

        manager.insertTextAt(3, "XX");
        assertManagerInvariants(manager);

        manager.deleteTextAt(1, 4);
        assertManagerInvariants(manager);

        manager.insertTextAt(manager.getText().length, "!");
        assertManagerInvariants(manager);

        manager.insertTextAt(0, ">");
        assertManagerInvariants(manager);
        expect(getAbsoluteLabels(manager)).toEqual([]);
    });

    it("preserves visible segment invariants for mixed labeled and unlabeled text", () => {
        const manager = makeBasicSegmentManager<TestStyle, ManagedTestLabel>(
            "Alice met Bob in Wonderland.",
            [
                makeLabel("1", 0, 5, "alice"),
                makeLabel("2", 10, 13, "bob"),
                makeLabel("3", 17, 27, "place"),
            ],
            1,
        );

        assertManagerInvariants(manager);
        expect(getAbsoluteLabels(manager)).toEqual([
            { id: "1", start: 0, end: 5, name: "alice" },
            { id: "2", start: 10, end: 13, name: "bob" },
            { id: "3", start: 17, end: 27, name: "place" },
        ]);

        manager.insertTextAt(6, "quietly ");
        assertManagerInvariants(manager);
        expect(getAbsoluteLabels(manager)).toEqual([
            { id: "1", start: 0, end: 5, name: "alice" },
            { id: "2", start: 18, end: 21, name: "bob" },
            { id: "3", start: 25, end: 35, name: "place" },
        ]);

        manager.deleteTextAt(6, 4);
        assertManagerInvariants(manager);
        expect(getAbsoluteLabels(manager)).toEqual([
            { id: "1", start: 0, end: 5, name: "alice" },
            { id: "2", start: 14, end: 17, name: "bob" },
            { id: "3", start: 21, end: 31, name: "place" },
        ]);
    });

    it("notifies subscribers when the manager changes", () => {
        const manager = makeBasicSegmentManager<TestStyle, ManagedTestLabel>("abcd", []);
        const calls: number[] = [];
        const unsubscribe = manager.subscribe(() => {
            calls.push(1);
        });

        manager.insertTextAt(2, "X");
        unsubscribe();
        manager.deleteTextAt(1, 1);

        expect(calls).toHaveLength(1);
    });
});
