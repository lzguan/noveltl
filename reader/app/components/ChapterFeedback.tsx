import { type FormEvent, type MouseEvent, useEffect, useRef, useState } from "react";
import { useFetcher } from "react-router";
import {
	FEEDBACK_EMOJI_OPTIONS,
	FEEDBACK_ISSUE_CATEGORY_OPTIONS,
	type FeedbackAnchor,
	type FeedbackEmoji,
	type FeedbackIssueCategory,
} from "../lib/feedbackAnchor";
import { DEFAULT_MASCOT_CONFIG, type MascotConfig, type MascotState } from "../lib/mascot";
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
	mascot?: MascotConfig;
};

export function ChapterFeedbackWidget({
	contentHash,
	feedbackStatus,
	mascot = DEFAULT_MASCOT_CONFIG,
}: ChapterFeedbackWidgetProps) {
	const reactionFetcher = useFetcher<FeedbackActionData>();
	const detailedFetcher = useFetcher<FeedbackActionData>();
	const detailedFormRef = useRef<HTMLFormElement>(null);
	const [open, setOpen] = useState(feedbackStatus !== null);
	const [showNote, setShowNote] = useState(false);
	const [glowCount, setGlowCount] = useState(0);
	const [selectedEmoji, setSelectedEmoji] = useState<FeedbackEmoji | null>(null);

	const reactionSucceeded = reactionFetcher.data?.ok === true;
	const detailedSucceeded = detailedFetcher.data?.ok === true;
	const mascotState: MascotState =
		selectedEmoji ??
		(detailedSucceeded || feedbackStatus === "thanks" ? "happy" : open ? "listening" : "idle");

	useEffect(() => {
		if (detailedFetcher.state === "idle" && detailedFetcher.data?.ok) {
			detailedFormRef.current?.reset();
		}
	}, [detailedFetcher.state, detailedFetcher.data]);

	function handleMascotClick() {
		setGlowCount((count) => count + 1);
		setOpen((current) => {
			if (current) {
				setShowNote(false);
			}
			return !current;
		});
	}

	function handleReactionClick(event: MouseEvent<HTMLButtonElement>, emoji: FeedbackEmoji) {
		event.preventDefault();
		setGlowCount((count) => count + 1);
		if (emoji === selectedEmoji) {
			return;
		}
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
		setGlowCount((count) => count + 1);
		detailedFetcher.submit(formData, { method: "post" });
	}

	const reactionError =
		reactionFetcher.data && !reactionFetcher.data.ok ? reactionFetcher.data.error : null;
	const detailedError =
		detailedFetcher.data && !detailedFetcher.data.ok ? detailedFetcher.data.error : null;

	return (
		<section id="chapter-feedback" aria-label="Chapter feedback" className="mt-8">
			<div className="flex flex-wrap items-center gap-2">
				<button
					type="button"
					onClick={handleMascotClick}
					aria-expanded={open}
					aria-label={mascot.prompt}
					className="group inline-flex cursor-pointer items-center gap-2 rounded-full p-1 transition focus-visible:outline focus-visible:outline-ink"
				>
					<span
						key={glowCount}
						className={glowCount > 0 ? "inky-mascot-glow inline-flex" : "inline-flex"}
					>
						<FeedbackMascot state={mascotState} size="md" config={mascot} />
					</span>
					{!open ? (
						<span className="text-xs text-muted transition group-hover:text-ink">
							{mascot.prompt}
						</span>
					) : null}
				</button>

				{open ? (
					<form
						method="post"
						className="flex flex-wrap items-center gap-1.5"
						aria-label="Quick reactions"
					>
						<input type="hidden" name="kind" value="reaction" />
						<input type="hidden" name="contentHash" value={contentHash} />
						{FEEDBACK_EMOJI_OPTIONS.map((option, index) => {
							const isSelected = selectedEmoji === option.value;
							return (
								<button
									key={option.value}
									type="submit"
									name="emoji"
									value={option.value}
									title={option.label}
									aria-label={option.label}
									aria-pressed={isSelected}
									disabled={reactionFetcher.state !== "idle"}
									onClick={(event) => handleReactionClick(event, option.value)}
									style={{ animationDelay: `${index * 30}ms` }}
									className={`inky-option-circle inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border text-sm transition hover:bg-hover disabled:opacity-60 ${
										isSelected ? "border-ink bg-hover" : "border-line bg-page"
									}`}
								>
									<span aria-hidden="true">{option.icon}</span>
								</button>
							);
						})}

						<button
							type="button"
							title="More feedback"
							aria-label="More feedback"
							aria-expanded={showNote}
							onClick={() => setShowNote((current) => !current)}
							style={{
								animationDelay: `${FEEDBACK_EMOJI_OPTIONS.length * 30}ms`,
							}}
							className={`inky-option-circle inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border text-xs transition hover:bg-hover ${
								showNote
									? "border-ink bg-ink text-page"
									: "border-line bg-page text-ink"
							}`}
						>
							<span aria-hidden="true">✎</span>
						</button>

						{reactionSucceeded || feedbackStatus === "thanks" ? (
							<span role="status" className="ml-1 text-xs text-muted">
								Thanks!
							</span>
						) : null}
					</form>
				) : null}
			</div>

			{feedbackStatus === "error" ? (
				<p role="alert" className="mt-2 text-xs text-ink">
					Couldn&apos;t save feedback.
				</p>
			) : null}
			{reactionError ? (
				<p role="alert" className="mt-2 text-xs text-ink">
					{reactionError}
				</p>
			) : null}

			{open && showNote ? (
				<form
					ref={detailedFormRef}
					method="post"
					onSubmit={handleDetailedSubmit}
					className="mt-3 max-w-md space-y-2 rounded-lg border border-line bg-page p-3"
				>
					<input type="hidden" name="kind" value="detailed" />
					<input type="hidden" name="contentHash" value={contentHash} />

					<select
						name="category"
						aria-label="Category"
						defaultValue="comment"
						className="block w-full rounded border border-line bg-page px-2.5 py-1.5 text-sm text-ink"
					>
						<option value="comment">Comment</option>
						{FEEDBACK_ISSUE_CATEGORY_OPTIONS.map((option) => (
							<option key={option.value} value={option.value}>
								{option.label}
							</option>
						))}
					</select>

					<textarea
						name="message"
						aria-label="Feedback details"
						required
						rows={2}
						maxLength={2000}
						placeholder="Write a note..."
						className="block w-full rounded border border-line bg-page px-2.5 py-2 text-sm text-ink"
					/>

					{detailedError ? (
						<p role="alert" className="text-xs text-ink">
							{detailedError}
						</p>
					) : null}

					<div className="flex items-center justify-end gap-2">
						{detailedSucceeded ? (
							<span role="status" className="text-xs text-muted">
								Sent!
							</span>
						) : null}
						<button
							type="submit"
							disabled={detailedFetcher.state !== "idle"}
							className="cursor-pointer rounded border border-ink bg-ink px-3.5 py-1.5 text-xs font-medium text-page hover:opacity-90 disabled:opacity-50"
						>
							{detailedFetcher.state !== "idle" ? "Sending..." : "Send"}
						</button>
					</div>
				</form>
			) : null}
		</section>
	);
}

type FeedbackModeDockProps = {
	onExit: () => void;
	mascot?: MascotConfig;
};

export function FeedbackModeDock({
	onExit,
	mascot = DEFAULT_MASCOT_CONFIG,
}: FeedbackModeDockProps) {
	return (
		<div
			role="status"
			className="inky-pop-up fixed bottom-4 left-1/2 z-40 flex -translate-x-1/2 items-center gap-2.5 rounded-full border border-line bg-page/95 py-1.5 pr-2.5 pl-2 shadow-md backdrop-blur"
		>
			<FeedbackMascot state="listening" size="sm" config={mascot} />
			<span className="text-xs text-ink">Tap a word</span>
			<button
				type="button"
				onClick={onExit}
				aria-label="Exit feedback mode"
				className="cursor-pointer rounded-full border border-line px-2 py-0.5 text-xs text-muted hover:bg-hover hover:text-ink"
			>
				×
			</button>
		</div>
	);
}

type AnchoredFeedbackSheetProps = {
	anchor: FeedbackAnchor;
	contentHash: string;
	onClose: () => void;
	mascot?: MascotConfig;
};

export function AnchoredFeedbackSheet({
	anchor,
	contentHash,
	onClose,
	mascot = DEFAULT_MASCOT_CONFIG,
}: AnchoredFeedbackSheetProps) {
	const reactionFetcher = useFetcher<FeedbackActionData>();
	const sheetFetcher = useFetcher<FeedbackActionData>();
	const [showNote, setShowNote] = useState(false);
	const [glowCount, setGlowCount] = useState(1);
	const [selectedEmoji, setSelectedEmoji] = useState<FeedbackEmoji | null>(null);
	const [category, setCategory] = useState<FeedbackIssueCategory>("typo");
	const [message, setMessage] = useState("");

	const reactionSucceeded = reactionFetcher.data?.ok === true;
	const submitted = sheetFetcher.data?.ok === true;
	const reactionError =
		reactionFetcher.data && !reactionFetcher.data.ok ? reactionFetcher.data.error : null;
	const error = sheetFetcher.data && !sheetFetcher.data.ok ? sheetFetcher.data.error : null;
	const mascotState: MascotState = selectedEmoji ?? (submitted ? "happy" : "listening");

	useEffect(() => {
		function onKeyDown(event: KeyboardEvent) {
			if (event.key === "Escape") {
				onClose();
			}
		}
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [onClose]);

	function handleReactionClick(event: MouseEvent<HTMLButtonElement>, emoji: FeedbackEmoji) {
		event.preventDefault();
		setGlowCount((count) => count + 1);
		if (emoji === selectedEmoji) {
			return;
		}
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

	function handleSubmit(event: FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const formData = new FormData(event.currentTarget);
		formData.set("js", "1");
		setGlowCount((count) => count + 1);
		sheetFetcher.submit(formData, { method: "post" });
	}

	return (
		<section
			role="dialog"
			aria-modal="false"
			aria-label="Chapter feedback"
			className="inky-pop-up fixed bottom-4 left-1/2 z-50 w-[calc(100%-1.5rem)] max-w-md -translate-x-1/2"
		>
			{showNote ? (
				<div className="mb-2 rounded-xl border border-line bg-page/95 p-3 shadow-lg backdrop-blur">
					{submitted ? (
						<div className="flex items-center justify-between gap-3">
							<p role="status" className="text-xs text-muted">
								Thanks!
							</p>
							<button
								type="button"
								onClick={onClose}
								className="cursor-pointer rounded border border-ink bg-ink px-3 py-1 text-xs font-medium text-page hover:opacity-90"
							>
								Done
							</button>
						</div>
					) : (
						<form method="post" onSubmit={handleSubmit} className="space-y-2.5">
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
											className={`cursor-pointer rounded-full border px-2.5 py-1 text-xs transition ${
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

							<textarea
								name="message"
								aria-label="Feedback details"
								required
								rows={2}
								maxLength={2000}
								value={message}
								onChange={(event) => setMessage(event.target.value)}
								placeholder="Details..."
								className="block w-full rounded border border-line bg-page px-2.5 py-2 text-sm text-ink"
							/>

							{error ? (
								<p role="alert" className="text-xs text-ink">
									{error}
								</p>
							) : null}

							<div className="flex items-center justify-end gap-2">
								<button
									type="button"
									onClick={() => setShowNote(false)}
									className="cursor-pointer rounded border border-line px-3 py-1 text-xs text-muted hover:bg-hover hover:text-ink"
								>
									Cancel
								</button>
								<button
									type="submit"
									disabled={sheetFetcher.state !== "idle"}
									className="cursor-pointer rounded border border-ink bg-ink px-3.5 py-1 text-xs font-medium text-page hover:opacity-90 disabled:opacity-50"
								>
									{sheetFetcher.state !== "idle" ? "Sending..." : "Send"}
								</button>
							</div>
						</form>
					)}
				</div>
			) : null}

			<div className="rounded-2xl border border-line bg-page/95 px-3 py-2 shadow-lg backdrop-blur">
				<div className="mb-1.5 flex items-center justify-between gap-2">
					<span className="truncate text-xs text-muted">
						&ldquo;{anchor.quote}&rdquo;
					</span>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close"
						className="cursor-pointer rounded-full border border-line px-2 py-0.5 text-xs text-muted hover:bg-hover hover:text-ink"
					>
						×
					</button>
				</div>

				<div className="flex flex-wrap items-center gap-2">
					<span key={glowCount} className="inky-mascot-glow inline-flex shrink-0">
						<FeedbackMascot state={mascotState} size="md" config={mascot} />
					</span>

					<form
						method="post"
						className="flex flex-wrap items-center gap-1.5"
						aria-label="Quick reactions"
					>
						<input type="hidden" name="kind" value="reaction" />
						<input type="hidden" name="contentHash" value={contentHash} />
						{FEEDBACK_EMOJI_OPTIONS.map((option, index) => {
							const isSelected = selectedEmoji === option.value;
							return (
								<button
									key={option.value}
									type="submit"
									name="emoji"
									value={option.value}
									title={option.label}
									aria-label={option.label}
									aria-pressed={isSelected}
									disabled={reactionFetcher.state !== "idle"}
									onClick={(event) => handleReactionClick(event, option.value)}
									style={{ animationDelay: `${index * 30}ms` }}
									className={`inky-option-circle inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border text-sm transition hover:bg-hover disabled:opacity-60 ${
										isSelected ? "border-ink bg-hover" : "border-line bg-page"
									}`}
								>
									<span aria-hidden="true">{option.icon}</span>
								</button>
							);
						})}

						<button
							type="button"
							title="Write a note"
							aria-label="Write a note"
							aria-expanded={showNote}
							onClick={() => setShowNote((current) => !current)}
							style={{
								animationDelay: `${FEEDBACK_EMOJI_OPTIONS.length * 30}ms`,
							}}
							className={`inky-option-circle inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border text-xs transition hover:bg-hover ${
								showNote
									? "border-ink bg-ink text-page"
									: "border-line bg-page text-ink"
							}`}
						>
							<span aria-hidden="true">✎</span>
						</button>

						{reactionSucceeded ? (
							<span role="status" className="ml-1 text-xs text-muted">
								Thanks!
							</span>
						) : null}
					</form>
				</div>

				{reactionError ? (
					<p role="alert" className="mt-1.5 text-xs text-ink">
						{reactionError}
					</p>
				) : null}
			</div>
		</section>
	);
}
