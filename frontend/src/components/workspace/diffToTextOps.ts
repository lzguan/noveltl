import { diffMain, diffCleanupSemantic, DIFF_EQUAL, DIFF_INSERT, DIFF_DELETE } from "diff-match-patch-es";
import { type TextOp } from "../../types/novel";

/**
 * Compute minimal TextOps to transform oldText into newText.
 * Uses diff-match-patch for character-level diffing, which produces
 * small ops that preserve more labels (the backend drops labels
 * straddling edit boundaries).
 *
 * The returned ops are ordered so the backend can apply them
 * sequentially via apply_text_ops.
 */
export function diffToTextOps(oldText: string, newText: string): TextOp[] {
    if (oldText === newText) return [];

    const diffs = diffMain(oldText, newText);
    diffCleanupSemantic(diffs);

    const ops: TextOp[] = [];
    let pos = 0; // position in the evolving (partially-transformed) text

    for (const [type, text] of diffs) {
        if (type === DIFF_EQUAL) {
            pos += text.length;
        } else if (type === DIFF_DELETE) {
            ops.push({ op: "delete", start: pos, text });
            // pos stays the same — text was removed at this position
        } else if (type === DIFF_INSERT) {
            ops.push({ op: "insert", start: pos, text });
            pos += text.length;
        }
    }

    return ops;
}
