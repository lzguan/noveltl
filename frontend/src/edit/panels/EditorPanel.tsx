import { useCallback, useMemo, useRef, useState } from "react";
import { DynamicLabeledText, type Caret } from "@/components/labeled-text-lib/react/DynamicLabeledText";
import type { SegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import {
	makeBoxOverlayRenderer,
	makePlainTextRenderer,
	resolvePlainTextPoint,
	type TextRenderer,
	type OverlayRenderer,
} from "@/components/labeled-text-lib/react/Renderer";
import type { LabelStyle, EditorMode } from "../managers/editorManager";
import type { LProvId } from "../controller/types/idTypes";
import type { IDLabelOp } from "../controller/types/dataTypes";
import type { EditorData } from "../hooks/useEditorState";
import type { TextOp } from "@/api/models";

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
	sm: SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>;
	onSetCaret: (c: Caret | null) => void;
	onTextOp: (op: TextOp) => void;
}) {
	const onSetCaretRef = useRef(onSetCaret);
	onSetCaretRef.current = onSetCaret;
	const onTextOpRef = useRef(onTextOp);
	onTextOpRef.current = onTextOp;

	const [caret, setCaret] = useState<Caret>({
		anchor: 0,
		focus: 0,
		visible: false,
	});

	const editMode = mode === "edit";
	const labelMode = mode === "label";

	const renderText = useMemo<TextRenderer<LabelStyle, StyledLabel<LabelStyle>>>(
		() => makePlainTextRenderer(),
		[],
	);

	const renderOverlay = useMemo<
		OverlayRenderer<LabelStyle, StyledLabel<LabelStyle>>
	>(
		() =>
			makeBoxOverlayRenderer<LabelStyle, StyledLabel<LabelStyle>>(
				labelToBoxStyle,
				resolvePlainTextPoint,
			),
		[],
	);

	const render = useMemo(
		() => ({
			renderText,
			renderOverlay,
			renderCaret: () => (
				<div
					className="caret-overlay"
					style={{
						position: "absolute",
						inset: 0,
						pointerEvents: "none",
						overflow: "hidden",
						display: caret.visible ? "block" : "none",
					}}
				/>
			),
		}),
		[renderText, renderOverlay, caret.visible],
	);

	const handlePointerDown = useCallback(
		({ caret: c, manager }: { caret: Caret; manager: typeof sm }) => {
			if (labelMode) {
				const ids = manager.labelsAt(c.focus);
				if (ids.length === 0) return;
			} else if (editMode) {
				setCaret(c);
				onSetCaretRef.current(c);
			}
		},
		[labelMode, editMode],
	);

	const handleBeforeInput = useCallback(
		({ caret: c, manager }: { caret: Caret; manager: typeof sm }) => {
			if (!editMode) return;
			const min = Math.min(c.anchor, c.focus);
			const max = Math.max(c.anchor, c.focus);
			if (max > min) {
				const deleted = manager.getText().slice(min, max);
				onTextOpRef.current({ op: "delete", start: min, text: deleted });
			}
		},
		[editMode],
	);

	const handleInput = useCallback(
		({ event, caret: c }: { event: React.FormEvent<HTMLDivElement>; caret: Caret }) => {
			if (!editMode) return;
			const inserted =
				event.currentTarget.textContent?.slice(c.anchor, c.focus) ?? "";
			if (inserted) {
				onTextOpRef.current({ op: "insert", start: c.anchor, text: inserted });
			}
		},
		[editMode],
	);

	const caretVisible = editMode || labelMode;

	return (
		<DynamicLabeledText<LabelStyle, StyledLabel<LabelStyle>, LProvId>
			caret={{ ...caret, visible: caretVisible }}
			manager={sm}
			render={render}
			containerStyle={{
				padding: "1rem",
				fontFamily: "monospace",
				fontSize: "0.875rem",
				lineHeight: "1.75",
				whiteSpace: "pre-wrap",
				height: "100%",
				overflow: "auto",
				position: "relative",
			}}
			overlayStyle={{
				position: "absolute",
				inset: 0,
				pointerEvents: "none",
			}}
			caretOverlayStyle={{
				position: "absolute",
				inset: 0,
				pointerEvents: "none",
				overflow: "hidden",
			}}
			onPointerDown={handlePointerDown}
			onBeforeInput={handleBeforeInput}
			onInput={handleInput}
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
		<EditorInner
			mode={mode}
			sm={data.segmentManager}
			onSetCaret={onSetCaret}
			onTextOp={onTextOp}
			key={data.segmentManager.getText().length}
		/>
	);
}
