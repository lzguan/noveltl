import { useEffect, useRef, useState, type JSX } from "react";
import type { SegmentManager } from "../core/segmentManager";
import type { StyledLabel, Style } from "../core/types";
import type { Renderer } from "./Renderer";

type Caret = {
    anchor : number;
    focus : number;
    visible : boolean;
}

type CaretRenderer = ({caret, containerRef, overlayRef} : { caret : Caret, containerRef : React.RefObject<HTMLDivElement | null>, overlayRef : React.RefObject<HTMLDivElement | null> }) => JSX.Element;

type EditorRenderer<S extends Style, L extends StyledLabel<S>> = Renderer<S, L> & {
    renderCaret : CaretRenderer;
}

type CallbackParams<S extends Style, L extends StyledLabel<S>, E extends React.SyntheticEvent<HTMLDivElement>> = {
    event : E;
    manager : SegmentManager<S, L>;
    caret : Caret;
}

type EditorCallbacks<S extends Style, L extends StyledLabel<S>> = {
    onPointerDown? : ({event, manager, caret} : CallbackParams<S, L, React.PointerEvent<HTMLDivElement>>) => void;
    onPointerMove? : ({event, manager, caret} : CallbackParams<S, L, React.PointerEvent<HTMLDivElement>>) => void;
    onPointerUp? : ({event, manager, caret} : CallbackParams<S, L, React.PointerEvent<HTMLDivElement>>) => void;
    onClick? : ({event, manager, caret} : CallbackParams<S, L, React.MouseEvent<HTMLDivElement>>) => void;
    onDoubleClick? : ({event, manager, caret} : CallbackParams<S, L, React.MouseEvent<HTMLDivElement>>) => void;
    onKeyDown? : ({event, manager, caret} : CallbackParams<S, L, React.KeyboardEvent<HTMLDivElement>>) => void;
    onKeyUp? : ({event, manager, caret} : CallbackParams<S, L, React.KeyboardEvent<HTMLDivElement>>) => void;
    onCopy? : ({event, manager, caret} : CallbackParams<S, L, React.ClipboardEvent<HTMLDivElement>>) => void;
    onCut? : ({event, manager, caret} : CallbackParams<S, L, React.ClipboardEvent<HTMLDivElement>>) => void;
    onPaste? : ({event, manager, caret} : CallbackParams<S, L, React.ClipboardEvent<HTMLDivElement>>) => void;
    onCompositionStart? : ({event, manager, caret} : CallbackParams<S, L, React.CompositionEvent<HTMLDivElement>>) => void;
    onCompositionUpdate? : ({event, manager, caret} : CallbackParams<S, L, React.CompositionEvent<HTMLDivElement>>) => void;
    onCompositionEnd? : ({event, manager, caret} : CallbackParams<S, L, React.CompositionEvent<HTMLDivElement>>) => void;
    onBeforeInput? : ({event, manager, caret} : CallbackParams<S, L, React.InputEvent<HTMLDivElement>>) => void;
    onInput? : ({event, manager, caret} : CallbackParams<S, L, React.InputEvent<HTMLDivElement>>) => void;
    onFocus? : ({event, manager, caret} : CallbackParams<S, L, React.FocusEvent<HTMLDivElement>>) => void;
    onBlur? : ({event, manager, caret} : CallbackParams<S, L, React.FocusEvent<HTMLDivElement>>) => void;
}

function DynamicLabeledText<S extends Style, L extends StyledLabel<S>>(
    { caret, manager, render, containerStyle, overlayStyle, caretOverlayStyle, ...callbacks } : { caret: Caret, manager : SegmentManager<S, L>, render : EditorRenderer<S, L>, containerStyle?: React.CSSProperties, overlayStyle?: React.CSSProperties, caretOverlayStyle?: React.CSSProperties } & EditorCallbacks<S, L>
) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const overlayRef = useRef<HTMLDivElement | null>(null);
    const caretOverlayRef = useRef<HTMLDivElement | null>(null);
    const hiddenContentEditableRef = useRef<HTMLDivElement | null>(null);
    const [segments, setSegments] = useState(() => manager.getSegments());


    useEffect(() => {
        const unsubscribe = manager.subscribe(() => {
            setSegments(manager.getSegments());
        });

        return () => {
            unsubscribe();
        }
    }, [manager]);

    return (
        <div
            onPointerDown={e => { hiddenContentEditableRef.current?.focus(); callbacks.onPointerDown?.({ event: e, manager, caret }) }} 
            onPointerMove={e => callbacks.onPointerMove?.({ event: e, manager, caret })} 
            onPointerUp={e => callbacks.onPointerUp?.({ event: e, manager, caret })} 
            onDoubleClick={e => callbacks.onDoubleClick?.({ event: e, manager, caret })}
        >
            <div
                ref={containerRef} 
                style={{position: "relative", ...containerStyle}}>

                <div ref={overlayRef} style={{ position: "absolute", inset: 0, pointerEvents: "none", ...overlayStyle }}>
                    {render.renderOverlay ? segments.map((segment) => (
                        render.renderOverlay ? <render.renderOverlay key={segment.start} segment={segment} containerRef={containerRef} overlayRef={overlayRef} /> : null
                    )) : null}
                </div>
                {segments.map((segment) => (
                    <span key={segment.start} data-segment-start={segment.start} style={{ whiteSpace: "pre-wrap" }}>
                        {render.renderText({ segment })}
                    </span>
                ))}
                <div ref={caretOverlayRef} style={{ position: "absolute", inset: 0, pointerEvents: "none", ...caretOverlayStyle }}>
                    {render.renderCaret({ caret, containerRef, overlayRef: caretOverlayRef })}
                </div>
            </div>
            <div ref={hiddenContentEditableRef} contentEditable={true} key={"__hidden__"} style={{ position: "absolute", left: -9999, width: 0, height: 0, overflow: "hidden" }} 
                
                onKeyDown={e => callbacks.onKeyDown?.({ event: e, manager, caret })} 
                onKeyUp={e => callbacks.onKeyUp?.({ event: e, manager, caret })} 
                onCopy={e => callbacks.onCopy?.({ event: e, manager, caret })} 
                onCut={e => callbacks.onCut?.({ event: e, manager, caret })} 
                onPaste={e => callbacks.onPaste?.({ event: e, manager, caret })} 
                onCompositionStart={e => callbacks.onCompositionStart?.({ event: e, manager, caret })} 
                onCompositionUpdate={e => callbacks.onCompositionUpdate?.({ event: e, manager, caret })} 
                onCompositionEnd={e => callbacks.onCompositionEnd?.({ event: e, manager, caret })}
                onFocus={e => callbacks.onFocus?.({ event: e, manager, caret })}
                onBlur={e => callbacks.onBlur?.({ event: e, manager, caret })}
                onBeforeInput={e => callbacks.onBeforeInput?.({ event: e, manager, caret})}
                onInput={e => callbacks.onInput?.({ event: e, manager, caret })}
            />
        </div>
    );
}

export {
    DynamicLabeledText,
};