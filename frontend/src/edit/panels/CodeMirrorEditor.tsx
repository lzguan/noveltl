import { useEffect, useMemo, useRef } from "react";
import {
	Compartment,
	EditorState,
	type Range,
	StateEffect,
	StateField,
} from "@codemirror/state";
import { Decoration, type DecorationSet, EditorView, keymap } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import type { SegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import { blue, green, red, toHex } from "@/components/labeled-text-lib/builtin/colors";
import type { Caret } from "@/components/labeled-text-lib/react/DynamicLabeledText";
import type { EditorMode, LabelStyle } from "../managers/editorManager";
import type { LProvId } from "../controller/types/idTypes";
import type { TextOp } from "@/api/models";

type SM = SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>;

/**
 * Replaces the current decoration set wholesale. Dispatched whenever the
 * SegmentManager notifies that labels changed.
 */
const setDecorations = StateEffect.define<DecorationSet>();

function labelMark(color: number): Decoration {
	return Decoration.mark({
		attributes: {
			style: `background-color: rgba(${red(color)}, ${green(color)}, ${blue(color)}, 0.2); border-bottom: 2px solid ${toHex(color)};`,
		},
	});
}

/**
 * Projects the SegmentManager's labels into CodeMirror mark decorations using
 * absolute document offsets. Segment labels are stored segment-relative, so we
 * offset by `segment.start`.
 */
function buildDecorations(sm: SM): DecorationSet {
	const ranges: Range<Decoration>[] = [];
	for (const segment of sm.getSegments()) {
		for (const label of segment.labels) {
			const from = segment.start + label.interval.start;
			const to = segment.start + label.interval.end;
			if (to <= from) continue;
			if (!label.style[1].visible) continue;
			ranges.push(labelMark(label.style[0].color).range(from, to));
		}
	}
	return Decoration.set(ranges, true);
}

const editorTheme = EditorView.theme({
	"&": {
		height: "100%",
		fontSize: "1.05rem",
		fontFamily: '"Helvetica Neue", Helvetica, Arial, ui-sans-serif, system-ui, sans-serif',
	},
	".cm-content": { lineHeight: "1.75", padding: "1rem" },
	".cm-scroller": { overflow: "auto" },
	"&.cm-focused": { outline: "none" },
});

/**
 * CodeMirror-backed editing surface. Phase 1: CodeMirror owns the rendered
 * document and caret (fixing IME / end-of-text caret), reads labels from the
 * existing SegmentManager as read-only decorations, and emits TextOps for the
 * controller. Label creation, validation wiring, and SegmentManager removal are
 * intentionally deferred.
 */
export function CodeMirrorEditor({
	sm,
	mode,
	onSetCaret,
	onTextOp,
}: {
	sm: SM;
	mode: EditorMode;
	onSetCaret: (c: Caret | null) => void;
	onTextOp: (op: TextOp) => void;
}) {
	const containerRef = useRef<HTMLDivElement | null>(null);
	const viewRef = useRef<EditorView | null>(null);

	const onSetCaretRef = useRef(onSetCaret);
	onSetCaretRef.current = onSetCaret;
	const onTextOpRef = useRef(onTextOp);
	onTextOpRef.current = onTextOp;
	const modeRef = useRef(mode);
	modeRef.current = mode;

	const editableCompartment = useMemo(() => new Compartment(), []);

	useEffect(() => {
		const parent = containerRef.current;
		if (!parent) return;

		const decorationsField = StateField.define<DecorationSet>({
			create: () => buildDecorations(sm),
			update(deco, tr) {
				let next = deco.map(tr.changes);
				for (const effect of tr.effects) {
					if (effect.is(setDecorations)) next = effect.value;
				}
				return next;
			},
			provide: (field) => EditorView.decorations.from(field),
		});

		const view = new EditorView({
			parent,
			state: EditorState.create({
				doc: sm.getText(),
				extensions: [
					history(),
					keymap.of([...defaultKeymap, ...historyKeymap]),
					EditorView.lineWrapping,
					decorationsField,
					editableCompartment.of(EditorView.editable.of(modeRef.current === "edit")),
					editorTheme,
					EditorView.updateListener.of((update) => {
						if (update.docChanged) {
							let shift = 0;
							update.changes.iterChanges((fromA, toA, _fromB, _toB, inserted) => {
								const removed = update.startState.doc.sliceString(fromA, toA);
								const start = fromA + shift;
								if (removed.length > 0) {
									onTextOpRef.current({ op: "delete", start, text: removed });
								}
								const insertedText = inserted.toString();
								if (insertedText.length > 0) {
									onTextOpRef.current({ op: "insert", start, text: insertedText });
								}
								shift += insertedText.length - removed.length;
							});
						}
						if (update.docChanged || update.selectionSet || update.focusChanged) {
							const main = update.state.selection.main;
							onSetCaretRef.current({
								anchor: main.anchor,
								focus: main.head,
								visible: update.view.hasFocus,
							});
						}
					}),
				],
			}),
		});
		viewRef.current = view;

		const unsubscribe = sm.subscribe(() => {
			view.dispatch({ effects: setDecorations.of(buildDecorations(sm)) });
		});

		return () => {
			unsubscribe();
			view.destroy();
			viewRef.current = null;
		};
	}, [sm, editableCompartment]);

	useEffect(() => {
		viewRef.current?.dispatch({
			effects: editableCompartment.reconfigure(EditorView.editable.of(mode === "edit")),
		});
	}, [mode, editableCompartment]);

	return <div ref={containerRef} style={{ height: "100%" }} />;
}
