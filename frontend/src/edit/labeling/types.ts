import type { Color } from "@/edit/lib/text-model/builtin/colors";
import type { LGProvId } from "../controller/types/idTypes";

/**
 * Metadata a label can carry besides its text range and word.
 */
export type LabelMeta = { entityGroup?: string; score?: number; dirty: boolean };

/**
 * A label group that a new label can be added to.
 */
export type AddTarget = { labelGroupId: LGProvId; groupName: string; color: Color };

/**
 * An existing label, as the editor needs to see it for hit-testing/deletion.
 */
export type EditorLabel = AddTarget & { start: number; end: number; word: string };

export type LabelRange = { start: number; end: number; word: string };

/**
 * Read side: resolves which labels/groups are relevant to an editor interaction.
 *
 * This is the swappable seam: the default implementation resolves only the
 * active label group, but it can be replaced (e.g. with a getter-backed
 * resolver that returns every label overlapping a position across all groups)
 * without touching the editor, menu, or form.
 */
export interface LabelSource {
	/** Labels (in actionable groups) overlapping the given document offset. */
	labelsAt(pos: number): EditorLabel[];
	/** Candidate target group(s) for adding a label. */
	addTargets(): AddTarget[];
}

/**
 * Write side: emits label operations. The default implementation forwards to the
 * controller via the editor manager.
 */
export interface LabelSink {
	add(target: LGProvId, range: LabelRange, meta: LabelMeta): void;
	remove(target: LGProvId, range: LabelRange): void;
}

export type LabelEditing = { source: LabelSource; sink: LabelSink };
