export const FEEDBACK_EMOJIS = ["love", "funny", "shocked", "sad", "confused"] as const;
export type FeedbackEmoji = (typeof FEEDBACK_EMOJIS)[number];

export const FEEDBACK_EMOJI_OPTIONS: ReadonlyArray<{
	value: FeedbackEmoji;
	icon: string;
	label: string;
}> = [
	{ value: "love", icon: "❤️", label: "Love" },
	{ value: "funny", icon: "😂", label: "Funny" },
	{ value: "shocked", icon: "😮", label: "Shocked" },
	{ value: "sad", icon: "😢", label: "Sad" },
	{ value: "confused", icon: "🤔", label: "Confused" },
];

export const FEEDBACK_ISSUE_CATEGORIES = [
	"typo",
	"mistranslation",
	"name_consistency",
	"formatting",
	"other",
] as const;
export type FeedbackIssueCategory = (typeof FEEDBACK_ISSUE_CATEGORIES)[number];

export const FEEDBACK_ISSUE_CATEGORY_OPTIONS: ReadonlyArray<{
	value: FeedbackIssueCategory;
	label: string;
}> = [
	{ value: "typo", label: "Typo" },
	{ value: "mistranslation", label: "Mistranslation" },
	{ value: "name_consistency", label: "Name consistency" },
	{ value: "formatting", label: "Formatting" },
	{ value: "other", label: "Other" },
];

export type FeedbackAnchor = {
	paragraphIndex: number;
	startOffset: number;
	endOffset: number;
	quote: string;
};

export function isFeedbackEmoji(value: unknown): value is FeedbackEmoji {
	return typeof value === "string" && FEEDBACK_EMOJIS.some((emoji) => emoji === value);
}

export function isFeedbackIssueCategory(value: unknown): value is FeedbackIssueCategory {
	return (
		typeof value === "string" &&
		FEEDBACK_ISSUE_CATEGORIES.some((category) => category === value)
	);
}

const CJK_NO_SPACE_RE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u;
const LETTER_OR_NUMBER_RE = /[\p{L}\p{N}]/u;
const WHITESPACE_RE = /\s/u;
const MAX_QUOTE_LENGTH = 300;

function isCjkNoSpace(ch: string | undefined): boolean {
	return ch !== undefined && CJK_NO_SPACE_RE.test(ch);
}

function isSpacedWordChar(ch: string | undefined): boolean {
	return ch !== undefined && LETTER_OR_NUMBER_RE.test(ch) && !CJK_NO_SPACE_RE.test(ch);
}

function isInternalConnector(ch: string | undefined): boolean {
	return ch === "'" || ch === "’" || ch === "-";
}

function isWhitespace(ch: string | undefined): boolean {
	return ch === undefined || WHITESPACE_RE.test(ch);
}

function findNearestTargetIndex(text: string, initialPos: number): number | null {
	const len = text.length;
	if (len === 0) return null;

	let pos = Math.max(0, Math.min(initialPos, len));
	if (pos === len) {
		pos = len - 1;
	}

	if (isSpacedWordChar(text[pos]) || isCjkNoSpace(text[pos])) {
		return pos;
	}
	if (pos > 0 && (isSpacedWordChar(text[pos - 1]) || isCjkNoSpace(text[pos - 1]))) {
		return pos - 1;
	}

	for (let distance = 1; distance < len; distance += 1) {
		const right = pos + distance;
		if (right < len && (isSpacedWordChar(text[right]) || isCjkNoSpace(text[right]))) {
			return right;
		}
		const left = pos - distance;
		if (left >= 0 && (isSpacedWordChar(text[left]) || isCjkNoSpace(text[left]))) {
			return left;
		}
	}

	if (!isWhitespace(text[pos])) {
		return pos;
	}
	for (let distance = 1; distance < len; distance += 1) {
		const right = pos + distance;
		if (right < len && !isWhitespace(text[right])) return right;
		const left = pos - distance;
		if (left >= 0 && !isWhitespace(text[left])) return left;
	}
	return null;
}

function segmentCjkSpan(
	text: string,
	runStart: number,
	runEnd: number,
	pos: number,
): [number, number] {
	const run = text.slice(runStart, runEnd);
	const relativePos = pos - runStart;

	if (run.length <= 4) {
		return [runStart, runEnd];
	}

	if (typeof Intl !== "undefined" && typeof Intl.Segmenter === "function") {
		const segmenter = new Intl.Segmenter("zh", { granularity: "word" });
		for (const part of segmenter.segment(run)) {
			const segStart = part.index;
			const segEnd = part.index + part.segment.length;
			if (relativePos >= segStart && relativePos < segEnd) {
				return [runStart + segStart, runStart + segEnd];
			}
		}
	}

	const start = Math.max(runStart, pos - 1);
	const end = Math.min(runEnd, pos + 3);
	return [start, end];
}

export function extractWordAnchor(
	paragraphText: string,
	paragraphIndex: number,
	caretOffset: number,
): FeedbackAnchor | null {
	if (!Number.isInteger(paragraphIndex) || paragraphIndex < 0) {
		return null;
	}
	if (paragraphText.trim().length === 0) {
		return null;
	}

	const targetPos = findNearestTargetIndex(paragraphText, Math.trunc(caretOffset));
	if (targetPos === null) {
		return null;
	}

	let start = targetPos;
	let end = targetPos + 1;

	if (isSpacedWordChar(paragraphText[targetPos])) {
		while (start > 0) {
			const prev = paragraphText[start - 1];
			if (isSpacedWordChar(prev)) {
				start -= 1;
			} else if (isInternalConnector(prev) && isSpacedWordChar(paragraphText[start - 2])) {
				start -= 2;
			} else {
				break;
			}
		}
		while (end < paragraphText.length) {
			const next = paragraphText[end];
			if (isSpacedWordChar(next)) {
				end += 1;
			} else if (isInternalConnector(next) && isSpacedWordChar(paragraphText[end + 1])) {
				end += 2;
			} else {
				break;
			}
		}
	} else if (isCjkNoSpace(paragraphText[targetPos])) {
		let runStart = targetPos;
		let runEnd = targetPos + 1;
		while (runStart > 0 && isCjkNoSpace(paragraphText[runStart - 1])) {
			runStart -= 1;
		}
		while (runEnd < paragraphText.length && isCjkNoSpace(paragraphText[runEnd])) {
			runEnd += 1;
		}
		[start, end] = segmentCjkSpan(paragraphText, runStart, runEnd, targetPos);
	} else {
		while (start > 0 && !isWhitespace(paragraphText[start - 1])) {
			start -= 1;
		}
		while (end < paragraphText.length && !isWhitespace(paragraphText[end])) {
			end += 1;
		}
	}

	if (end - start > MAX_QUOTE_LENGTH) {
		end = start + MAX_QUOTE_LENGTH;
	}

	while (start < end && isWhitespace(paragraphText[start])) {
		start += 1;
	}
	while (end > start && isWhitespace(paragraphText[end - 1])) {
		end -= 1;
	}

	if (end <= start) {
		return null;
	}

	return {
		paragraphIndex,
		startOffset: start,
		endOffset: end,
		quote: paragraphText.slice(start, end),
	};
}

export function resolveCaretOffsetInElement(
	container: Element,
	targetNode: Node,
	targetOffset: number,
): number | null {
	if (!container.contains(targetNode)) {
		return null;
	}

	let accumulated = 0;

	function walk(node: Node): number | null {
		if (node === targetNode) {
			if (node.nodeType === Node.TEXT_NODE) {
				const textLen = node.textContent?.length ?? 0;
				return accumulated + Math.max(0, Math.min(targetOffset, textLen));
			}
			const limit = Math.max(0, Math.min(targetOffset, node.childNodes.length));
			for (let i = 0; i < limit; i += 1) {
				const child = node.childNodes[i];
				if (child) {
					accumulated += child.textContent?.length ?? 0;
				}
			}
			return accumulated;
		}

		if (node.nodeType === Node.TEXT_NODE) {
			accumulated += node.textContent?.length ?? 0;
			return null;
		}

		for (let i = 0; i < node.childNodes.length; i += 1) {
			const child = node.childNodes[i];
			if (!child) continue;
			const found = walk(child);
			if (found !== null) return found;
		}
		return null;
	}

	return walk(container);
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null;
}

export function resolvePointToCaret(
	clientX: number,
	clientY: number,
): { node: Node; offset: number } | null {
	if (typeof document === "undefined") {
		return null;
	}

	const caretPosFn: unknown = Reflect.get(document, "caretPositionFromPoint");
	if (typeof caretPosFn === "function") {
		const position: unknown = Reflect.apply(caretPosFn, document, [clientX, clientY]);
		if (
			isObjectRecord(position) &&
			position.offsetNode instanceof Node &&
			typeof position.offset === "number"
		) {
			return { node: position.offsetNode, offset: position.offset };
		}
	}

	const caretRangeFn: unknown = Reflect.get(document, "caretRangeFromPoint");
	if (typeof caretRangeFn === "function") {
		const range: unknown = Reflect.apply(caretRangeFn, document, [clientX, clientY]);
		if (range instanceof Range) {
			return { node: range.startContainer, offset: range.startOffset };
		}
	}

	const selection = window.getSelection();
	if (selection && selection.anchorNode) {
		return { node: selection.anchorNode, offset: selection.anchorOffset };
	}

	return null;
}
