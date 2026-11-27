import { type FormEvent, type MouseEvent, useEffect, useRef, useState } from "react";
import { useFetcher } from "react-router";
import {
	FEEDBACK_EMOJI_OPTIONS,
	FEEDBACK_ISSUE_CATEGORY_OPTIONS,
	type FeedbackAnchor,
	type FeedbackEmoji,
	type FeedbackIssueCategory,
} from "../lib/feedbackAnchor";
import { FeedbackMascot } from "./FeedbackMascot";

export type FeedbackActionData =
	| {
			ok: true;
			kind: "reaction" | "issue" | "comment";
			emoji?: FeedbackEmoji;
			feedbackId: string;
	  }
	| {
			ok: false;
			error: string;
	  };

type ChapterFeedbackWidgetProps = {
	contentHash: string;
	feedbackStatus: "thanks" | "error" | null;
};

export function ChapterFeedbackWidget({ contentHash, feedbackStatus }: ChapterFeedbackWidgetProps) {
	const reactionFetcher = useFetcher<FeedbackActionData>();
	const detailedFetcher = useFetcher<FeedbackActionData>();
	const detailedFormRef = useRef<HTMLFormElement>(null);
	const [selectedEmoji, setSelectedEmoji] = useState<FeedbackEmoji | null>(null);

	const reactionSucceeded = reactionFetcher.data?.ok === true;
	const detailedSucceeded = detailedFetcher.data?.ok === true;
	const hasThankYou = reactionSucceeded || detailedSucceeded || feedbackStatus === "thanks";
	const mascotMood = hasThankYou ? "happy" : "idle";

	useEffect(() => {
		if (detailedFetcher.state === "idle" && detailedFetcher.data?.ok) {
			detailedFormRef.current?.reset();
		}
	}, [detailedFetcher.state, detailedFetcher.data]);

	function handleReactionClick(event: MouseEvent<HTMLButtonElement>, emoji: FeedbackEmoji) {
		event.preventDefault();
		setSelectedEmoji(emoji);
		reactionFetcher.submit(
			{
				kind: "reaction",
				emoji,
				contentHash,
				js: "1",
			},
			{ method: "post" },
		);
	}

	function handleDetailedSubmit(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const formData = new FormData(event.currentTarget);
		formData.set("js", "1");
		detailedFetcher.submit(formData, { method: "post" });
	}

	const reactionError =
		reactionFetcher.data && !reactionFetcher.data.ok ? reactionFetcher.data.error : null;
	const detailedError =
		detailedFetcher.data && !detailedFetcher.data.ok ? detailedFetcher.data.error : null;

	return (
		<section id="chapter-feedback" aria-label="Chapter feedback" className="mt-10">
			<details
				open={feedbackStatus !== null}
				className="rounded-lg border border-line bg-page"
			>
				<summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 select-none hover:bg-hover [&::-webkit-details-marker]:hidden">
					<FeedbackMascot mood={mascotMood} size="md" />
					<div className="min-w-0 flex-1">
						<span className="inline-block rounded-full border border-line bg-page px-3 py-1 text-sm font-medium text-ink">
							Give Inky feedback
						</span>
						<p className="mt-1 text-xs text-muted">
							Quick chapter reaction or report a translation note
						</p>
					</div>
				</summary>

				<div className="space-y-4 border-t border-line px-4 py-4">
					{feedbackStatus === "thanks" ? (
						<p
							role="status"
							className="rounded border border-line bg-hover px-3 py-2 text-sm text-ink"
						>
							Thanks! Inky received your feedback.
						</p>
					) : null}
					{feedbackStatus === "error" ? (
						<p
							role="alert"
							className="rounded border border-line bg-hover px-3 py-2 text-sm text-ink"
						>
							Inky couldn&apos;t save that feedback. Please check your note and try
							again.
						</p>
					) : null}

					<div>
						<p className="mb-2 text-xs font-medium text-muted">
							How did this chapter feel?
						</p>
						<form
							method="post"
							className="flex flex-wrap gap-2"
							aria-label="Quick reactions"
						>
							<input type="hidden" name="kind" value="reaction" />
							<input type="hidden" name="contentHash" value={contentHash} />
							{FEEDBACK_EMOJI_OPTIONS.map((option) => {
								const isSelected = selectedEmoji === option.value;
								return (
									<button
										key={option.value}
										type="submit"
										name="emoji"
										value={option.value}
										aria-label={option.label}
										aria-pressed={isSelected}
										disabled={reactionFetcher.state !== "idle"}
										onClick={(event) =>
											handleReactionClick(event, option.value)
										}
										className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition hover:bg-hover disabled:opacity-60 ${
											isSelected
												? "border-ink bg-hover font-medium text-ink"
												: "border-line text-ink"
										}`}
									>
										<span aria-hidden="true">{option.icon}</span>
										<span>{option.label}</span>
									</button>
								);
							})}
						</form>
						{reactionSucceeded ? (
							<p role="status" className="mt-2 text-xs text-muted">
								Thanks! Inky noted your reaction.
							</p>
						) : null}
						{reactionError ? (
							<p role="alert" className="mt-2 text-xs text-ink">
								{reactionError}
							</p>
						) : null}
					</div>

					<details className="rounded border border-line">
						<summary className="cursor-pointer px-3 py-2 text-sm font-medium text-ink hover:bg-hover">
							More detailed feedback
						</summary>
						<form
							ref={detailedFormRef}
							method="post"
							onSubmit={handleDetailedSubmit}
							className="space-y-3 border-t border-line p-3"
						>
							<input type="hidden" name="kind" value="detailed" />
							<input type="hidden" name="contentHash" value={contentHash} />

							<label className="block text-xs font-medium text-muted">
								<span>Category</span>
								<select
									name="category"
									defaultValue="comment"
									className="mt-1 block w-full rounded border border-line bg-page px-2.5 py-2 text-sm text-ink"
								>
									<option value="comment">Comment</option>
									{FEEDBACK_ISSUE_CATEGORY_OPTIONS.map((option) => (
										<option key={option.value} value={option.value}>
											{option.label}
										</option>
									))}
								</select>
							</label>

							<label className="block text-xs font-medium text-muted">
								<span>Details</span>
								<textarea
									name="message"
									required
									rows={3}
									maxLength={2000}
									placeholder="Share a thought, typo, or translation note..."
									className="mt-1 block w-full rounded border border-line bg-page px-2.5 py-2 text-sm text-ink"
								/>
							</label>

							{detailedError ? (
								<p role="alert" className="text-xs text-ink">
									{detailedError}
								</p>
							) : null}
							{detailedSucceeded ? (
								<p role="status" className="text-xs text-muted">
									Thanks! Inky delivered your note.
								</p>
							) : null}

							<div className="flex justify-end">
								<button
									type="submit"
									disabled={detailedFetcher.state !== "idle"}
									className="rounded border border-ink bg-ink px-3.5 py-1.5 text-sm font-medium text-page hover:opacity-90 disabled:opacity-50"
								>
									{detailedFetcher.state !== "idle"
										? "Sending..."
										: "Send feedback"}
								</button>
							</div>
						</form>
					</details>
				</div>
			</details>
		</section>
	);
}

type AnchoredFeedbackSheetProps = {
	anchor: FeedbackAnchor;
	contentHash: string;
	onClose: () => void;
};

export function AnchoredFeedbackSheet({
	anchor,
	contentHash,
	onClose,
}: AnchoredFeedbackSheetProps) {
	const sheetFetcher = useFetcher<FeedbackActionData>();
	const [category, setCategory] = useState<FeedbackIssueCategory>("typo");
	const [message, setMessage] = useState("");

	const submitted = sheetFetcher.data?.ok === true;
	const error = sheetFetcher.data && !sheetFetcher.data.ok ? sheetFetcher.data.error : null;

	useEffect(() => {
		function onKeyDown(event: KeyboardEvent) {
			if (event.key === "Escape") {
				onClose();
			}
		}
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [onClose]);

	function handleSubmit(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const formData = new FormData(event.currentTarget);
		formData.set("js", "1");
		sheetFetcher.submit(formData, { method: "post" });
	}

	return (
		<>
			<div
				className="fixed inset-0 z-40 bg-black/25 sm:bg-transparent"
				onClick={onClose}
				aria-hidden="true"
			/>
			<section
				role="dialog"
				aria-modal="false"
				aria-label="Report issue on selected passage"
				className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-2xl border-t border-line bg-page p-4 shadow-lg sm:inset-x-auto sm:right-6 sm:bottom-6 sm:w-96 sm:rounded-xl sm:border"
			>
				<div className="flex items-start justify-between gap-3">
					<div className="flex items-center gap-2.5">
						<FeedbackMascot mood={submitted ? "happy" : "listening"} size="sm" />
						<div>
							<h2 className="text-sm font-semibold text-ink">
								{submitted ? "Thanks for flagging that!" : "Spot an issue?"}
							</h2>
							<p className="text-xs text-muted">
								Paragraph {anchor.paragraphIndex + 1}
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close feedback sheet"
						className="rounded border border-line px-2 py-1 text-xs text-muted hover:bg-hover hover:text-ink"
					>
						Close
					</button>
				</div>

				<blockquote className="mt-3 rounded border border-line bg-hover px-3 py-2 text-sm text-ink">
					&ldquo;{anchor.quote}&rdquo;
				</blockquote>

				{submitted ? (
					<div className="mt-4 space-y-3">
						<p role="status" className="text-sm text-muted">
							Inky saved your report. Tap another word to keep going, or close this
							panel.
						</p>
						<div className="flex justify-end">
							<button
								type="button"
								onClick={onClose}
								className="rounded border border-ink bg-ink px-3.5 py-1.5 text-sm font-medium text-page hover:opacity-90"
							>
								Done
							</button>
						</div>
					</div>
				) : (
					<form method="post" onSubmit={handleSubmit} className="mt-3 space-y-3">
						<input type="hidden" name="kind" value="issue" />
						<input type="hidden" name="category" value={category} />
						<input type="hidden" name="contentHash" value={contentHash} />
						<input
							type="hidden"
							name="anchorParagraphIndex"
							value={String(anchor.paragraphIndex)}
						/>
						<input
							type="hidden"
							name="anchorStartOffset"
							value={String(anchor.startOffset)}
						/>
						<input
							type="hidden"
							name="anchorEndOffset"
							value={String(anchor.endOffset)}
						/>
						<input type="hidden" name="anchorQuote" value={anchor.quote} />

						<div
							className="flex flex-wrap gap-1.5"
							role="group"
							aria-label="Issue type"
						>
							{FEEDBACK_ISSUE_CATEGORY_OPTIONS.map((option) => {
								const active = category === option.value;
								return (
									<button
										key={option.value}
										type="button"
										aria-pressed={active}
										onClick={() => setCategory(option.value)}
										className={`rounded-full border px-2.5 py-1 text-xs transition ${
											active
												? "border-ink bg-ink font-medium text-page"
												: "border-line text-ink hover:bg-hover"
										}`}
									>
										{option.label}
									</button>
								);
							})}
						</div>

						<label className="block text-xs font-medium text-muted">
							<span>What looks off?</span>
							<textarea
								name="message"
								required
								rows={3}
								maxLength={2000}
								value={message}
								onChange={(event) => setMessage(event.target.value)}
								placeholder="Describe the typo, phrasing, or name mismatch..."
								className="mt-1 block w-full rounded border border-line bg-page px-2.5 py-2 text-sm text-ink"
							/>
						</label>

						{error ? (
							<p role="alert" className="text-xs text-ink">
								{error}
							</p>
						) : null}

						<div className="flex items-center justify-end gap-2">
							<button
								type="button"
								onClick={onClose}
								className="rounded border border-line px-3 py-1.5 text-sm text-muted hover:bg-hover hover:text-ink"
							>
								Cancel
							</button>
							<button
								type="submit"
								disabled={sheetFetcher.state !== "idle"}
								className="rounded border border-ink bg-ink px-3.5 py-1.5 text-sm font-medium text-page hover:opacity-90 disabled:opacity-50"
							>
								{sheetFetcher.state !== "idle" ? "Sending..." : "Submit"}
							</button>
						</div>
					</form>
				)}
			</section>
		</>
	);
}
