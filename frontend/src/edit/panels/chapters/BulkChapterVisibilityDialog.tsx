import { useState } from "react";
import { actionUpdateChaptersVisibilityNovelsNovelIdChaptersVisibilityPost } from "@/api/endpoints/default/default";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import type { ProvChapter } from "../../controller/types/idTypes";

type ParsedBound = { ok: true; value: number | null } | { ok: false };

function parseChapterBound(raw: string): ParsedBound {
	const trimmed = raw.trim();
	if (!trimmed) return { ok: true, value: null };
	if (!/^-?\d+$/.test(trimmed)) return { ok: false };
	const parsed = Number.parseInt(trimmed, 10);
	return Number.isSafeInteger(parsed) ? { ok: true, value: parsed } : { ok: false };
}

export function BulkChapterVisibilityDialog({
	novelId,
	chapters,
	onUpdated,
	onClose,
}: {
	novelId: string;
	chapters: readonly ProvChapter[];
	onUpdated: (chapterNums: readonly number[], isPublic: boolean) => void;
	onClose: () => void;
}) {
	const [start, setStart] = useState("");
	const [end, setEnd] = useState("");
	const [submitting, setSubmitting] = useState<"public" | "private" | null>(null);
	const [error, setError] = useState<string | null>(null);

	const parsedStart = parseChapterBound(start);
	const parsedEnd = parseChapterBound(end);

	let rangeError: string | null = null;
	if (!parsedStart.ok || !parsedEnd.ok) {
		rangeError = "Chapter numbers must be whole integers.";
	} else if (
		parsedStart.value !== null &&
		parsedEnd.value !== null &&
		parsedStart.value > parsedEnd.value
	) {
		rangeError = "Start chapter must be less than or equal to end chapter.";
	}

	const startNum = parsedStart.ok ? parsedStart.value : null;
	const endNum = parsedEnd.ok ? parsedEnd.value : null;
	const matching =
		rangeError === null
			? chapters.filter(
					(chapter) =>
						(startNum === null || chapter.chapterNum >= startNum) &&
						(endNum === null || chapter.chapterNum <= endNum),
				)
			: [];
	const publicCount = matching.filter((chapter) => chapter.chapterIsPublic).length;
	const privateCount = matching.length - publicCount;

	const submit = async (isPublic: boolean) => {
		if (rangeError !== null || submitting !== null) return;
		setSubmitting(isPublic ? "public" : "private");
		setError(null);
		try {
			const resp = await actionUpdateChaptersVisibilityNovelsNovelIdChaptersVisibilityPost(
				novelId,
				{
					start: startNum,
					end: endNum,
					isPublic,
				},
			);
			if (resp.status !== 200) {
				setError(apiErrorMessage(resp.data, "Could not update chapter visibility."));
				return;
			}
			onUpdated(resp.data.updatedChapterNums, resp.data.isPublic);
			onClose();
		} catch (err: unknown) {
			setError(requestErrorMessage(err));
		} finally {
			setSubmitting(null);
		}
	};

	const actionsDisabled = submitting !== null || rangeError !== null;

	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<DialogTitle>Chapter visibility</DialogTitle>
					<DialogDescription>
						Publish or unpublish a chapter range (inclusive). Leave both blank to update
						all chapters.
					</DialogDescription>
				</DialogHeader>
				<FieldGroup className="gap-3">
					<div className="grid grid-cols-2 gap-2">
						<Field>
							<FieldLabel htmlFor="bulk-visibility-start">From chapter</FieldLabel>
							<Input
								id="bulk-visibility-start"
								inputMode="numeric"
								placeholder="First"
								value={start}
								disabled={submitting !== null}
								onChange={(event) => setStart(event.target.value)}
							/>
						</Field>
						<Field>
							<FieldLabel htmlFor="bulk-visibility-end">To chapter</FieldLabel>
							<Input
								id="bulk-visibility-end"
								inputMode="numeric"
								placeholder="Last"
								value={end}
								disabled={submitting !== null}
								onChange={(event) => setEnd(event.target.value)}
							/>
						</Field>
					</div>
					{rangeError === null ? (
						<p className="text-xs text-muted-foreground">
							Matches {matching.length} of {chapters.length} chapters ({publicCount}{" "}
							public, {privateCount} private).
						</p>
					) : (
						<p role="alert" className="text-xs text-destructive">
							{rangeError}
						</p>
					)}
				</FieldGroup>
				{error !== null && (
					<p role="alert" className="text-xs text-destructive">
						{error}
					</p>
				)}
				<DialogFooter>
					<Button type="button" variant="outline" onClick={onClose}>
						Cancel
					</Button>
					<Button
						type="button"
						variant="secondary"
						disabled={actionsDisabled}
						onClick={() => void submit(false)}
					>
						{submitting === "private" ? "Updating..." : "Make private"}
					</Button>
					<Button
						type="button"
						disabled={actionsDisabled}
						onClick={() => void submit(true)}
					>
						{submitting === "public" ? "Updating..." : "Make public"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
