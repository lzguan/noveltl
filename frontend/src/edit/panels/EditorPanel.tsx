import { useMemo, useRef, useState } from "react";
import { DynamicLabeledText, type Caret } from "@/components/labeled-text-lib/react/DynamicLabeledText";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import {
	makeBoxOverlayRenderer,
	makePlainTextRenderer,
	resolvePlainTextPoint,
} from "@/components/labeled-text-lib/react/Renderer";
import type { LabelStyle, EditorMode } from "../managers/editorManager";
import type { LProvId } from "../controller/types/idTypes";
import type { IDLabelOp } from "../controller/types/dataTypes";
import type { EditorData } from "../hooks/useEditorState";
import type { TextOp } from "@/api/models";
import {
	pointerHandler,
	keyHandler,
	inputHandler,
	focusHandler,
	blurHandler,
	copyHandler,
	cutHandler,
	pasteHandler,
} from "../utils/editorCallbacks";

function labelToBoxStyle(style: LabelStyle): React.CSSProperties {
	const c = style[0].color;
	const cursor = style[1].cursorStatus;
	return {
		backgroundColor: `rgba(${(c >> 16) & 0xff}, ${(c >> 8) & 0xff}, ${c & 0xff}, 0.2)`,
		borderBottom: `2px solid #${c.toString(16).padStart(6, "0")}`,
		cursor: cursor === "clicked" ? "text" : cursor === "hovered" ? "pointer" : "default",
	};
}

function EditorInner({
	mode,
	sm,
	onSetCaret,
	onTextOp,
}: {
	mode: EditorMode;
	sm: import("@/components/labeled-text-lib/core/segmentManager").SegmentManager<
		LabelStyle,
		StyledLabel<LabelStyle>,
		LProvId
	>;
	onSetCaret: (c: Caret | null) => void;
	onTextOp: (op: TextOp) => void;
}) {
	const modeRef = useRef(mode);
	modeRef.current = mode;

	const onSetCaretRef = useRef(onSetCaret);
	onSetCaretRef.current = onSetCaret;
	const onTextOpRef = useRef(onTextOp);
	onTextOpRef.current = onTextOp;

	const [caret, setCaret] = useState<Caret>({ anchor: 0, focus: 0, visible: false });
	const caretRef = useRef(caret);
	caretRef.current = caret;

	const managerRef = useRef(sm);
	managerRef.current = sm;

	const renderText = useMemo(
		() => makePlainTextRenderer<LabelStyle, StyledLabel<LabelStyle>>(),
		[],
	);
	const renderOverlay = useMemo(
		() => makeBoxOverlayRenderer<LabelStyle, StyledLabel<LabelStyle>>(labelToBoxStyle, resolvePlainTextPoint),
		[],
	);
	const renderCaret = useMemo(
		() =>
			({
				caret: c,
				containerRef,
			}: {
				caret: Caret;
				containerRef: React.RefObject<HTMLDivElement | null>;
				overlayRef: React.RefObject<HTMLDivElement | null>;
			}) => {
				if (!c.visible || c.anchor !== c.focus) return <></>;
				const container = containerRef.current;
				if (!container) return <></>;
				const focus = Math.min(c.focus, managerRef.current.getText().length);
				const spans = container.querySelectorAll<HTMLSpanElement>("span[data-segment-start]");
				let target: HTMLSpanElement | null = null;
				let off = 0;
				for (const s of spans) {
					const start = parseInt(s.getAttribute("data-segment-start")!, 10);
					const len = (s.textContent ?? "").length;
					if (focus >= start && focus <= start + len) { target = s; off = focus - start; break; }
				}
				if (!target) {
					const last = spans[spans.length - 1];
					if (!last) return <></>;
					target = last;
					off = (last.textContent ?? "").length;
				}
				const tn = target.firstChild;
				if (!tn || tn.nodeType !== Node.TEXT_NODE) return <></>;
				const r = document.createRange();
				r.setStart(tn, Math.min(off, tn.textContent?.length ?? 0));
				r.collapse(true);
				const rect = r.getBoundingClientRect();
				const cr = container.getBoundingClientRect();
				return (
					<div
						className="caret-blinking"
						style={{
							position: "absolute",
							left: rect.left - cr.left,
							top: rect.top - cr.top,
							width: 2,
							height: rect.height || 16,
							backgroundColor: "currentColor",
						}}
					/>
				);
			},
		[],
	);

	const render = useMemo(
		() => ({ renderText, renderOverlay, renderCaret }),
		[renderText, renderOverlay, renderCaret],
	);

	const caretVisible = mode === "edit" || mode === "label";

	return (
		<DynamicLabeledText<LabelStyle, StyledLabel<LabelStyle>, LProvId>
			caret={{ ...caret, visible: caretVisible }}
			manager={sm}
			render={render}
			containerStyle={{
				padding: "1rem",
				fontFamily: '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif',
				fontSize: "0.875rem",
				lineHeight: "1.75",
				whiteSpace: "pre-wrap",
				height: "100%",
				overflow: "auto",
				position: "relative",
			}}
			overlayStyle={{ position: "absolute", inset: 0, pointerEvents: "none" }}
			caretOverlayStyle={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}
			onPointerDown={pointerHandler(caretRef, setCaret, onSetCaretRef.current)}
			onKeyDown={keyHandler(modeRef, caretRef, setCaret, onSetCaretRef.current, onTextOpRef)}
			onInput={inputHandler()}
			onFocus={focusHandler(setCaret)}
			onBlur={blurHandler(setCaret)}
			onCopy={copyHandler()}
			onCut={cutHandler(caretRef, setCaret, onSetCaretRef.current, onTextOpRef)}
			onPaste={pasteHandler(caretRef, setCaret, onSetCaretRef.current, onTextOpRef)}
		/>
	);
}

export function EditorPanel({
	data,
	mode,
	onSetCaret,
	onTextOp,
	onLabelOp: _onLabelOp,
}: {
	data: EditorData;
	mode: EditorMode;
	onSetCaret: (c: Caret | null) => void;
	onTextOp: (op: TextOp) => void;
	onLabelOp: (op: IDLabelOp) => void;
}) {
	if (data.loading) {
		return (
			<div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
				Loading...
			</div>
		);
	}
	return (
		<div className="flex-1 overflow-hidden">
			<EditorInner mode={mode} sm={data.segmentManager} onSetCaret={onSetCaret} onTextOp={onTextOp} />
		</div>
	);
}
