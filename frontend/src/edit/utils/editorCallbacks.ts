import type { Caret } from "@/components/labeled-text-lib/react/DynamicLabeledText";
import type { SegmentManager } from "@/components/labeled-text-lib/core/segmentManager";
import type { StyledLabel } from "@/components/labeled-text-lib/core/types";
import type { LabelStyle, EditorMode } from "../managers/editorManager";
import type { LProvId } from "../controller/types/idTypes";
import type { TextOp } from "@/api/models";

type SM = SegmentManager<LabelStyle, StyledLabel<LabelStyle>, LProvId>;

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

// ---- helpers --------------------------------------------------------------

function applyCaret(
	caretRef: React.RefObject<Caret>,
	setCaret: (c: Caret) => void,
	onSetCaret: (c: Caret | null) => void,
	c: Caret,
) {
	caretRef.current = c;
	setCaret(c);
	onSetCaret(c);
}

function commitTextDelete(
	text: string,
	cur: Caret,
	direction: "backward" | "forward",
	onTextOp: (op: TextOp) => void,
	caretRef: React.RefObject<Caret>,
	setCaret: (c: Caret) => void,
	onSetCaret: (c: Caret | null) => void,
) {
	const start = Math.min(cur.anchor, cur.focus);
	const end = Math.max(cur.anchor, cur.focus);

	if (end > start) {
		onTextOp({ op: "delete", start, text: text.slice(start, end) });
		applyCaret(caretRef, setCaret, onSetCaret, { anchor: start, focus: start, visible: true });
		return;
	}

	if (direction === "backward" && start > 0) {
		onTextOp({ op: "delete", start: start - 1, text: text.slice(start - 1, start) });
		applyCaret(caretRef, setCaret, onSetCaret, { anchor: start - 1, focus: start - 1, visible: true });
		return;
	}

	if (direction === "forward" && start < text.length) {
		onTextOp({ op: "delete", start, text: text.slice(start, start + 1) });
		applyCaret(caretRef, setCaret, onSetCaret, { anchor: start, focus: start, visible: true });
	}
}

function commitTextInsert(
	text: string,
	cur: Caret,
	inserted: string,
	onTextOp: (op: TextOp) => void,
	caretRef: React.RefObject<Caret>,
	setCaret: (c: Caret) => void,
	onSetCaret: (c: Caret | null) => void,
) {
	if (inserted.length === 0) return;

	const start = Math.min(cur.anchor, cur.focus);
	const end = Math.max(cur.anchor, cur.focus);

	if (end > start) {
		onTextOp({ op: "delete", start, text: text.slice(start, end) });
	}

	onTextOp({ op: "insert", start, text: inserted });
	const next = start + inserted.length;
	applyCaret(caretRef, setCaret, onSetCaret, { anchor: next, focus: next, visible: true });
}

// ---- click-to-offset -----------------------------------------------------

function getSegmentElement(target: EventTarget | null): HTMLElement | null {
	if (!(target instanceof Element)) return null;
	return target.closest("[data-segment-start]") as HTMLElement | null;
}

function textOffset(container: HTMLElement, node: Node, offset: number): number {
	const r = container.ownerDocument.createRange();
	r.setStart(container, 0);
	try { r.setEnd(node, offset); } catch { return container.textContent?.length ?? 0; }
	return r.toString().length;
}

function offsetFromPoint(container: HTMLElement, x: number, y: number): number {
	const doc = container.ownerDocument as Document & {
		caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
		caretRangeFromPoint?: (x: number, y: number) => Range | null;
	};
	const cp = doc.caretPositionFromPoint?.(x, y);
	if (cp && container.contains(cp.offsetNode)) return textOffset(container, cp.offsetNode, cp.offset);
	const cr = doc.caretRangeFromPoint?.(x, y);
	if (cr && container.contains(cr.startContainer)) return textOffset(container, cr.startContainer, cr.startOffset);
	return container.textContent?.length ?? 0;
}

function clickOffset(target: EventTarget | null, x: number, y: number, textLen: number): number {
	const seg = getSegmentElement(target);
	if (!seg) return textLen;
	const start = Number(seg.getAttribute("data-segment-start"));
	if (Number.isNaN(start)) return textLen;
	const local = clamp(offsetFromPoint(seg, x, y), 0, seg.textContent?.length ?? 0);
	return clamp(start + local, 0, textLen);
}

// ---- exported handlers ---------------------------------------------------

export function pointerHandler(
	caretRef: React.RefObject<Caret>,
	setCaret: (c: Caret) => void,
	onSetCaret: (c: Caret | null) => void,
) {
	return ({
		event,
		manager,
	}: {
		event: React.PointerEvent<HTMLDivElement>;
		manager: SM;
		caret: Caret;
	}) => {
		event.preventDefault();
		const pos = clickOffset(event.nativeEvent.target, event.nativeEvent.clientX, event.nativeEvent.clientY, manager.getText().length);
		applyCaret(caretRef, setCaret, onSetCaret, { anchor: pos, focus: pos, visible: true });
	};
}

export function keyHandler(
	modeRef: React.RefObject<EditorMode>,
	caretRef: React.RefObject<Caret>,
	setCaret: (c: Caret) => void,
	onSetCaret: (c: Caret | null) => void,
	onTextOpRef: React.RefObject<(op: TextOp) => void>,
) {
	return ({
		event,
		manager,
	}: {
		event: React.KeyboardEvent<HTMLDivElement>;
		manager: SM;
		caret: Caret;
	}) => {
		if (modeRef.current !== "edit") return;

		const text = manager.getText();
		const cur = caretRef.current;
		const tLen = text.length;
		const shift = event.shiftKey;
		const bStart = Math.min(cur.anchor, cur.focus);
		const bEnd = Math.max(cur.anchor, cur.focus);

		const onDelete = (dir: "backward" | "forward") =>
			commitTextDelete(text, cur, dir, onTextOpRef.current, caretRef, setCaret, onSetCaret);
		const onInsert = (s: string) =>
			commitTextInsert(text, cur, s, onTextOpRef.current, caretRef, setCaret, onSetCaret);

		// Ctrl+A
		if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "a") {
			event.preventDefault();
			applyCaret(caretRef, setCaret, onSetCaret, { anchor: 0, focus: tLen, visible: true });
			return;
		}

		// Skip meta shortcuts
		if ((event.metaKey || event.ctrlKey || event.altKey) && event.key.length === 1) return;

		switch (event.key) {
			case "ArrowLeft":
				event.preventDefault();
				{
					const p = clamp(shift ? cur.focus - 1 : bStart - 1, 0, tLen);
					applyCaret(caretRef, setCaret, onSetCaret,
						shift ? { anchor: cur.anchor, focus: p, visible: true }
							  : { anchor: p, focus: p, visible: true });
				}
				break;
			case "ArrowRight":
				event.preventDefault();
				{
					const p = clamp(shift ? cur.focus + 1 : bEnd + 1, 0, tLen);
					applyCaret(caretRef, setCaret, onSetCaret,
						shift ? { anchor: cur.anchor, focus: p, visible: true }
							  : { anchor: p, focus: p, visible: true });
				}
				break;
			case "Home":
				event.preventDefault();
				applyCaret(caretRef, setCaret, onSetCaret,
					shift ? { anchor: cur.anchor, focus: 0, visible: true }
						  : { anchor: 0, focus: 0, visible: true });
				break;
			case "End":
				event.preventDefault();
				applyCaret(caretRef, setCaret, onSetCaret,
					shift ? { anchor: cur.anchor, focus: tLen, visible: true }
						  : { anchor: tLen, focus: tLen, visible: true });
				break;
			case "Backspace":
				event.preventDefault();
				onDelete("backward");
				break;
			case "Delete":
				event.preventDefault();
				onDelete("forward");
				break;
			case "Enter":
				event.preventDefault();
				onInsert("\n");
				break;
			case "Tab":
				event.preventDefault();
				onInsert("    ");
				break;
			default:
				if (event.key.length === 1) {
					event.preventDefault();
					onInsert(event.key);
				}
		}
	};
}

export function inputHandler() {
	return ({ event }: { event: React.FormEvent<HTMLDivElement>; manager: SM; caret: Caret }) => {
		event.currentTarget.textContent = "";
	};
}

export function focusHandler(
	setCaret: (c: Caret) => void,
) {
	return ({ caret: c }: { event: React.FocusEvent<HTMLDivElement>; manager: SM; caret: Caret }) => {
		setCaret({ ...c, visible: true });
	};
}

export function blurHandler(
	setCaret: (c: Caret) => void,
) {
	return ({ caret: c }: { event: React.FocusEvent<HTMLDivElement>; manager: SM; caret: Caret }) => {
		setCaret({ ...c, visible: false });
	};
}

export function copyHandler() {
	return ({ event, manager, caret: c }: { event: React.ClipboardEvent<HTMLDivElement>; manager: SM; caret: Caret }) => {
		const start = Math.min(c.anchor, c.focus);
		const end = Math.max(c.anchor, c.focus);
		if (end <= start) return;
		const text = manager.getText().slice(start, end);
		if (!text) return;
		event.preventDefault();
		event.clipboardData.setData("text/plain", text);
	};
}

export function cutHandler(
	caretRef: React.RefObject<Caret>,
	setCaret: (c: Caret) => void,
	onSetCaret: (c: Caret | null) => void,
	onTextOpRef: React.RefObject<(op: TextOp) => void>,
) {
	return ({ event, manager, caret: c }: { event: React.ClipboardEvent<HTMLDivElement>; manager: SM; caret: Caret }) => {
		const start = Math.min(c.anchor, c.focus);
		const end = Math.max(c.anchor, c.focus);
		if (end <= start) return;
		const text = manager.getText().slice(start, end);
		event.preventDefault();
		event.clipboardData.setData("text/plain", text);
		onTextOpRef.current({ op: "delete", start, text });
		applyCaret(caretRef, setCaret, onSetCaret, { anchor: start, focus: start, visible: true });
	};
}

export function pasteHandler(
	caretRef: React.RefObject<Caret>,
	setCaret: (c: Caret) => void,
	onSetCaret: (c: Caret | null) => void,
	onTextOpRef: React.RefObject<(op: TextOp) => void>,
) {
	return ({ event, manager }: { event: React.ClipboardEvent<HTMLDivElement>; manager: SM; caret: Caret }) => {
		const text = event.clipboardData.getData("text/plain");
		if (!text) return;
		event.preventDefault();
		commitTextInsert(manager.getText(), caretRef.current, text, onTextOpRef.current, caretRef, setCaret, onSetCaret);
	};
}
