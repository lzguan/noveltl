import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { makeBasicSegmenter } from "../core/segmenters";
import type { Label } from "../core/types";
import { StaticLabeledText } from "../react/StaticLabeledText";
import {
    makeBoxOverlayRenderer,
    makePlainBoxRenderer,
    makePlainTextRenderer,
    type Renderer,
} from "../react/Renderer";

type TestStyle = {
    name: string;
};

type TestLabel = Label<TestStyle>;

function makeLabel(start: number, end: number, name: string): TestLabel {
    return {
        interval: { start, end },
        style: { name },
    };
}

class ResizeObserverMock {
    observe() {}
    disconnect() {}
}

function makeRect(left: number, width: number) {
    return {
        left,
        top: 0,
        right: left + width,
        bottom: 20,
        width,
        height: 20,
        x: left,
        y: 0,
        toJSON() {
            return this;
        },
    };
}

describe("LabeledText React integration", () => {
    beforeEach(() => {
        vi.stubGlobal("ResizeObserver", ResizeObserverMock);

        vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() =>
            makeRect(0, 0) as unknown as DOMRect,
        );

        vi.spyOn(document, "createRange").mockImplementation(() => {
            let start = 0;
            let end = 0;

            const resolvePoint = (node: Node, pos: number) => {
                const parent = node.parentElement as HTMLElement | null;
                const base = Number(parent?.dataset.base ?? 0);
                return base + pos;
            };

            return {
                setStart(node: Node, pos: number) {
                    start = resolvePoint(node, pos);
                },
                setEnd(node: Node, pos: number) {
                    end = resolvePoint(node, pos);
                },
                getClientRects() {
                    return [makeRect(start * 10, Math.max(0, end - start) * 10)] as unknown as DOMRectList;
                },
            } as unknown as Range;
        });
    });

    afterEach(() => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    it("renders segmented text directly through LabeledText", () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>();
        const renderer: Renderer<TestStyle, TestLabel> = {
            renderText: makePlainTextRenderer(),
        };

        const { container } = render(
            <StaticLabeledText
                text="abcdef"
                labels={[makeLabel(1, 3, "name")]}
                segment={segmenter}
                render={renderer}
            />,
        );

        expect(container.querySelectorAll("[data-segment-start]")).toHaveLength(3);
        expect(screen.getByText("a")).toBeInTheDocument();
        expect(screen.getByText("bc")).toBeInTheDocument();
        expect(screen.getByText("def")).toBeInTheDocument();
    });

    it("renders measured overlay boxes with the plain boxed renderer", async () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>();
        const renderer = makePlainBoxRenderer<TestStyle, TestLabel>((style) => ({
            backgroundColor: style.name === "name" ? "rgb(255, 0, 0)" : "rgb(0, 0, 255)",
        }));

        const { container } = render(
            <StaticLabeledText
                text="abcdef"
                labels={[makeLabel(1, 3, "name")]}
                segment={segmenter}
                render={renderer}
            />,
        );

        await waitFor(() => {
            const currentRedBoxes = Array.from(container.querySelectorAll("div")).filter(
                (element) => (element as HTMLDivElement).style.backgroundColor === "rgb(255, 0, 0)",
            );

            expect(currentRedBoxes).toHaveLength(1);
            expect((currentRedBoxes[0] as HTMLDivElement).style.left).toBe("0px");
            expect((currentRedBoxes[0] as HTMLDivElement).style.width).toBe("20px");
        });
    });

    it("supports overlay measurement across multiple text nodes with a custom resolver", async () => {
        const segmenter = makeBasicSegmenter<TestStyle, TestLabel>(2);
        const renderer: Renderer<TestStyle, TestLabel> = {
            renderText: ({ segment }) => (
                <>
                    <span data-base="0">{segment.text.slice(0, 2)}</span>
                    <span data-base="2">{segment.text.slice(2)}</span>
                </>
            ),
            renderOverlay: makeBoxOverlayRenderer(
                (style) => ({
                    backgroundColor: style.name === "name" ? "rgb(0, 128, 0)" : "rgb(0, 0, 0)",
                }),
                (element, _segment, offset) => {
                    const firstTextNode = element?.children[0]?.firstChild ?? null;
                    const secondTextNode = element?.children[1]?.firstChild ?? null;

                    if (offset <= 2) {
                        return { node: firstTextNode, pos: offset };
                    }

                    return { node: secondTextNode, pos: offset - 2 };
                },
            ),
        };

        const { container } = render(
            <StaticLabeledText
                text="abc"
                labels={[makeLabel(1, 3, "name")]}
                segment={segmenter}
                render={renderer}
            />,
        );

        await waitFor(() => {
            const currentGreenBoxes = Array.from(container.querySelectorAll("div")).filter(
                (element) => (element as HTMLDivElement).style.backgroundColor === "rgb(0, 128, 0)",
            );

            expect(currentGreenBoxes).toHaveLength(1);
            expect((currentGreenBoxes[0] as HTMLDivElement).style.left).toBe("10px");
            expect((currentGreenBoxes[0] as HTMLDivElement).style.width).toBe("20px");
        });
    });
});
