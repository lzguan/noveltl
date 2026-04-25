import { useEffect, useRef, useState } from "react";

import { makeBasicSegmentManager, type ManagedLabel, type SegmentManager } from "../core/segmentManager";
import type { StyledLabel, Style } from "../core/types";
import type { Renderer } from "./Renderer";

type ManagedLabeledTextProps<S extends Style, L extends StyledLabel<S>> = {
    initialText: string;
    initialLabels: ManagedLabel<S, L>[];
    gap?: number;
    render: Renderer<S, ManagedLabel<S, L>>;
    containerStyle?: React.CSSProperties;
    overlayStyle?: React.CSSProperties;
    onReady?: (manager: SegmentManager<S, L>) => void;
};

function ManagedLabeledText<S extends Style, L extends StyledLabel<S>>(
    props: ManagedLabeledTextProps<S, L>,
) {
    const {
        initialText,
        initialLabels,
        gap,
        render,
        containerStyle,
        overlayStyle,
        onReady,
    } = props;
    const containerRef = useRef<HTMLDivElement | null>(null);
    const overlayRef = useRef<HTMLDivElement | null>(null);
    const [manager] = useState(() =>
        makeBasicSegmentManager<S, L>(
            initialText,
            initialLabels,
            gap ?? 0,
        ),
    );
    const [segments, setSegments] = useState(() => manager.getSegments());

    useEffect(() => {
        return manager.subscribe(() => {
            setSegments(manager.getSegments());
        });
    }, [manager]);

    useEffect(() => {
        onReady?.(manager);
    }, [manager, onReady]);

    const Overlay = render.renderOverlay;
    const Text = render.renderText;

    return (
        <div>
            <div ref={containerRef} style={{ position: "relative", ...containerStyle }}>
                <div
                    ref={overlayRef}
                    style={{ position: "absolute", inset: 0, pointerEvents: "none", ...overlayStyle }}
                >
                    {Overlay
                        ? segments.map((segment) => (
                            <Overlay
                                key={segment.id}
                                segment={segment}
                                containerRef={containerRef}
                                overlayRef={overlayRef}
                            />
                        ))
                        : null}
                </div>
                {segments.map((segment) => (
                    <span key={segment.id} data-segment-start={segment.start} style={{ whiteSpace: "pre-wrap" }}>
                        <Text segment={segment} />
                    </span>
                ))}
            </div>
        </div>
    );
}

export {
    ManagedLabeledText,
};
export type {
    ManagedLabel,
};
