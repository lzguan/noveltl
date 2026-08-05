import type { TextReference } from "@/filters/types";
import { Effect } from "effect";
import { useCallback, useEffect, useState } from "react";
import type { NovelGetters } from "../controller/types/controllerTypes";
import {
	CCServId,
	CServId,
	LServId,
	type CProvId,
	type ProvChapter,
} from "../controller/types/idTypes";
import type { EditorData } from "./useEditorState";

export interface EditorTextHighlight {
	start: number;
	end: number;
}

export type ReferenceNavigationNotice =
	| { kind: "outdated"; chapterNum: number }
	| { kind: "unavailable"; chapterNum: number | null };

interface PendingReference {
	reference: TextReference;
	chapterId: CProvId;
	chapterNum: number;
}

export function useReferenceNavigation({
	chapterList,
	controllerGetters,
	editorData,
	switchChapter,
}: {
	chapterList: readonly ProvChapter[];
	controllerGetters: NovelGetters | null;
	editorData: EditorData;
	switchChapter: ((chapterId: CProvId) => void) | null;
}) {
	const [pendingReference, setPendingReference] = useState<PendingReference | null>(null);
	const [highlight, setHighlight] = useState<EditorTextHighlight | null>(null);
	const [notice, setNotice] = useState<ReferenceNavigationNotice | null>(null);

	const openTextReference = useCallback(
		(reference: TextReference) => {
			if (!controllerGetters || !switchChapter) return;
			const chapterId = Effect.runSync(
				controllerGetters.chapterIdFromServerId(CServId(reference.value.chapterId)),
			);
			if (chapterId === null) {
				setNotice({ kind: "unavailable", chapterNum: null });
				return;
			}
			const chapter = chapterList.find((item) => item.chapterId === chapterId);
			if (!chapter) {
				setNotice({ kind: "unavailable", chapterNum: null });
				return;
			}

			setHighlight(null);
			setNotice(null);
			setPendingReference({ reference, chapterId, chapterNum: chapter.chapterNum });
			switchChapter(chapterId);
		},
		[chapterList, controllerGetters, switchChapter],
	);

	useEffect(() => {
		if (!pendingReference || !controllerGetters || editorData.empty || editorData.loading)
			return;
		if (editorData.chapterId !== pendingReference.chapterId) return;

		const referencedContentId = Effect.runSync(
			controllerGetters.chapterContentIdFromServerId(
				CCServId(pendingReference.reference.value.chapterContentId),
			),
		);
		if (referencedContentId !== editorData.chapterContentId) {
			setNotice({ kind: "outdated", chapterNum: pendingReference.chapterNum });
			setPendingReference(null);
			return;
		}

		let range: EditorTextHighlight;
		if (pendingReference.reference.type === "textSpan") {
			range = {
				start: pendingReference.reference.value.start,
				end: pendingReference.reference.value.end,
			};
		} else {
			const labelId = Effect.runSync(
				controllerGetters.labelIdFromServerId(
					LServId(pendingReference.reference.value.labelId),
				),
			);
			if (labelId === null) {
				setNotice({ kind: "unavailable", chapterNum: pendingReference.chapterNum });
				setPendingReference(null);
				return;
			}
			try {
				const label = editorData.segmentManager.getLabel(labelId);
				range = { start: label.interval.start, end: label.interval.end };
			} catch {
				setNotice({ kind: "unavailable", chapterNum: pendingReference.chapterNum });
				setPendingReference(null);
				return;
			}
		}

		if (
			range.start < 0 ||
			range.end <= range.start ||
			range.end > editorData.segmentManager.getText().length
		) {
			setNotice({ kind: "unavailable", chapterNum: pendingReference.chapterNum });
			setPendingReference(null);
			return;
		}

		setHighlight(range);
		setPendingReference(null);
	}, [controllerGetters, editorData, pendingReference]);

	const clearHighlight = useCallback(() => setHighlight(null), []);
	const dismissNotice = useCallback(() => setNotice(null), []);

	return {
		highlight,
		notice,
		openTextReference,
		clearHighlight,
		dismissNotice,
	};
}
