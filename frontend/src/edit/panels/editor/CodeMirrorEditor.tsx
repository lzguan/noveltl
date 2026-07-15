import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Compartment, EditorState, type Range, StateEffect, StateField } from "@codemirror/state";
import { Decoration, type DecorationSet, EditorView, keymap } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import type { SegmentManager } from "@/edit/lib/text-model/core/segmentManager";
import type { StyledLabel } from "@/edit/lib/text-model/core/types";
import { blue, green, red, toHex } from "@/edit/lib/text-model/builtin/colors";
import type { Caret } from "../../hooks/useEditorState";
import type { EditorMode, LabelStyle } from "../../managers/editorManager";
import type { LProvId } from "../../controller/types/idTypes";
import type { TextOp } from "@/api/models";
import { LabelContextMenu } from "../../labeling/LabelContextMenu";
import { AddLabelForm } from "../../labeling/AddLabelForm";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import type { AddTarget, EditorLabel, LabelEditing } from "../../labeling/types";
import type { AutoLabelPreview } from "../../hooks/useAutoLabelPreview";

type SM = SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>;

/**
 * Replaces the current decoration set wholesale. Dispatched whenever the
 * SegmentManager notifies that labels changed.
 */
const setDecorations = StateEffect.define<DecorationSet>();
const setPreviewDecorations = StateEffect.define<DecorationSet>();

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

function previewMark(): Decoration {
	return Decoration.mark({ class: "cm-autolabel-preview" });
}

function buildPreviewDecorations(
	preview: AutoLabelPreview | null,
	docLength: number,
): DecorationSet {
	if (preview === null) return Decoration.none;
	const ranges: Range<Decoration>[] = [];
	for (const label of preview) {
		if (label.labelStart < 0 || label.labelEnd <= label.labelStart) continue;
		if (label.labelEnd > docLength) continue;
		ranges.push(previewMark().range(label.labelStart, label.labelEnd));
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
	".cm-autolabel-preview": {
		backgroundColor: "color-mix(in oklab, var(--primary) 10%, transparent)",
		borderBottom: "1px dashed var(--primary)",
	},
});

type MenuCtx = {
	selection: { from: number; to: number; word: string } | null;
	labels: EditorLabel[];
};

type FormState = {
	coords: { left: number; top: number };
	word: string;
	range: { from: number; to: number };
	targets: AddTarget[];
};

/**
 * CodeMirror-backed editing surface. CodeMirror owns the rendered document and
 * caret; labels are read-only decorations from the SegmentManager. In `label`
 * mode, a right-click context menu drives label add/delete via the injected
 * {@link LabelEditing} seam (text editing stays disabled).
 */
export function CodeMirrorEditor({
	sm,
	mode,
	onSetCaret,
	onTextOp,
	labeling,
	preview,
}: {
	sm: SM;
	mode: EditorMode;
	onSetCaret: (c: Caret | null) => void;
	onTextOp: (op: TextOp) => void;
	labeling: LabelEditing;
	preview: AutoLabelPreview | null;
}) {
	const containerRef = useRef<HTMLDivElement | null>(null);
	const viewRef = useRef<EditorView | null>(null);

	const onSetCaretRef = useRef(onSetCaret);
	onSetCaretRef.current = onSetCaret;
	const onTextOpRef = useRef(onTextOp);
	onTextOpRef.current = onTextOp;

	const [menuCtx, setMenuCtx] = useState<MenuCtx>({ selection: null, labels: [] });
	const [form, setForm] = useState<FormState | null>(null);

	const readOnlyCompartment = useMemo(() => new Compartment(), []);

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
		const previewDecorationsField = StateField.define<DecorationSet>({
			create: (state) => buildPreviewDecorations(preview, state.doc.length),
			update(deco, tr) {
				let next = tr.docChanged ? Decoration.none : deco;
				for (const effect of tr.effects) {
					if (effect.is(setPreviewDecorations)) next = effect.value;
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
					previewDecorationsField,
					readOnlyCompartment.of(EditorState.readOnly.of(mode !== "edit")),
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
									onTextOpRef.current({
										op: "insert",
										start,
										text: insertedText,
									});
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
		// `mode` is intentionally only used for the initial editable state; live
		// changes are handled by the reconfigure effect below.
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, [sm, readOnlyCompartment]);

	useEffect(() => {
		viewRef.current?.dispatch({
			effects: readOnlyCompartment.reconfigure(EditorState.readOnly.of(mode !== "edit")),
		});
	}, [mode, readOnlyCompartment]);

	useEffect(() => {
		const view = viewRef.current;
		if (!view) return;
		view.dispatch({
			effects: setPreviewDecorations.of(
				buildPreviewDecorations(preview, view.state.doc.length),
			),
		});
	}, [preview]);

	useEffect(() => {
		if (!form) return;
		const scroller = viewRef.current?.scrollDOM;
		if (!scroller) return;
		const onScroll = () => setForm(null);
		scroller.addEventListener("scroll", onScroll, { passive: true });
		return () => scroller.removeEventListener("scroll", onScroll);
	}, [form]);

	const handleContextMenu = useCallback(
		(event: React.MouseEvent<HTMLDivElement>) => {
			if (mode !== "label") return;
			const view = viewRef.current;
			if (!view) return;

			const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });

			let selection: MenuCtx["selection"] = null;
			const domSelection = window.getSelection();
			if (domSelection && domSelection.rangeCount > 0 && !domSelection.isCollapsed) {
				const range = domSelection.getRangeAt(0);
				if (
					view.dom.contains(range.startContainer) &&
					view.dom.contains(range.endContainer)
				) {
					const a = view.posAtDOM(range.startContainer, range.startOffset);
					const b = view.posAtDOM(range.endContainer, range.endOffset);
					const from = Math.min(a, b);
					const to = Math.max(a, b);
					if (to > from) {
						selection = { from, to, word: view.state.doc.sliceString(from, to) };
					}
				}
			}

			const labels = pos === null ? [] : labeling.source.labelsAt(pos);
			setMenuCtx({ selection, labels });
		},
		[mode, labeling],
	);

	const handleAdd = useCallback(() => {
		const view = viewRef.current;
		if (!view || !menuCtx.selection) return;
		const selection = menuCtx.selection;
		const targets = labeling.source.addTargets();
		const rect = view.coordsAtPos(selection.from);
		const coords = rect ? { left: rect.left, top: rect.bottom } : { left: 12, top: 12 };
		// Defer until the context menu has fully closed; otherwise the menu's
		// dismissal is treated as an outside-interaction that immediately closes
		// the popover.
		setTimeout(() => {
			setForm({
				coords,
				word: selection.word,
				range: { from: selection.from, to: selection.to },
				targets,
			});
		}, 0);
	}, [menuCtx, labeling]);

	const handleDelete = useCallback(
		(label: EditorLabel) => {
			labeling.sink.remove(label.labelGroupId, {
				start: label.start,
				end: label.end,
				word: label.word,
			});
		},
		[labeling],
	);

	const canAdd = menuCtx.selection !== null && labeling.source.addTargets().length > 0;

	return (
		<>
			<LabelContextMenu
				enabled={mode === "label"}
				hasSelection={menuCtx.selection !== null}
				canAdd={canAdd}
				labels={menuCtx.labels}
				onAdd={handleAdd}
				onDelete={handleDelete}
			>
				<div
					style={{ height: "100%" }}
					onContextMenu={handleContextMenu}
					onDragStart={(e) => {
						if (mode !== "edit") e.preventDefault();
					}}
				>
					<div ref={containerRef} style={{ height: "100%" }} />
				</div>
			</LabelContextMenu>
			{form && (
				<Popover
					modal
					open
					onOpenChange={(open) => {
						if (!open) setForm(null);
					}}
				>
					<PopoverAnchor asChild>
						<div
							style={{
								position: "fixed",
								left: form.coords.left,
								top: form.coords.top,
								width: 0,
								height: 0,
							}}
						/>
					</PopoverAnchor>
					<PopoverContent side="bottom" align="start" collisionPadding={8}>
						<AddLabelForm
							word={form.word}
							targets={form.targets}
							onSubmit={(target, meta) => {
								const op = {
									start: form.range.from,
									end: form.range.to,
									word: form.word,
								};
								console.log(
									"[addLabel] target=%s range=[%d,%d) word=%s",
									target,
									op.start,
									op.end,
									op.word,
									meta,
								);
								labeling.sink.add(target, op, meta);
								setForm(null);
							}}
							onCancel={() => setForm(null)}
						/>
					</PopoverContent>
				</Popover>
			)}
		</>
	);
}
