import { useEffect, useMemo, useRef, useState } from "react";
import {
	ArrowLeft,
	ChevronDown,
	ChevronLeft,
	ChevronRight,
	ChevronUp,
	FileText,
	Link2,
	Plus,
	Unlink2,
} from "lucide-react";
import {
	createNovelNovelsPost,
	readAllLanguagesLanguagesGet,
} from "@/api/endpoints/default/default";
import {
	acceptOutputsTranslationJobsJobIdAcceptPost,
	listOutputsTranslationJobsJobIdOutputsGet,
	readOutputTranslationJobsJobIdOutputsChapterIdGet,
} from "@/api/endpoints/translations/translations";
import {
	NovelType,
	TranslationAcceptBatchScopeMode,
	TranslationAcceptJobScopeMode,
	TranslationAcceptRangeScopeMode,
	TranslationAcceptRequestOnExisting,
	Visibility,
} from "@/api/models";
import type {
	Language,
	TranslationAcceptRequest,
	TranslationAcceptScope,
	TranslationOutputChapterDetail,
	TranslationOutputsRead,
	TranslationStageRead,
	TranslationTargetNovel,
} from "@/api/models";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import type { Loadable } from "@/lib/loadable";

type ScopeMode = "job" | "batch" | "range";

function parseScopeMode(value: string): ScopeMode {
	if (value === "batch" || value === "range") return value;
	return "job";
}

function parseOnExisting(value: string): TranslationAcceptRequestOnExisting {
	return value === TranslationAcceptRequestOnExisting.overwrite
		? TranslationAcceptRequestOnExisting.overwrite
		: TranslationAcceptRequestOnExisting.skip;
}

function findTargetLanguage(stages: readonly TranslationStageRead[]): string | null {
	for (let index = stages.length - 1; index >= 0; index -= 1) {
		const stage = stages[index];
		if (stage.action !== "translate") continue;
		const raw = stage.config.target_language ?? stage.config.targetLanguage;
		if (typeof raw === "string" && raw.trim().length > 0) return raw.trim();
	}
	return null;
}

function findMatchingLanguageCode(
	languages: readonly Language[],
	preferred: string | null,
): string | null {
	if (!preferred) return null;
	const needle = preferred.trim().toLowerCase();
	if (!needle) return null;
	const byCode = languages.find((language) => language.languageCode.toLowerCase() === needle);
	if (byCode) return byCode.languageCode;
	const byName = languages.find((language) => language.languageName.toLowerCase() === needle);
	if (byName) return byName.languageCode;
	return null;
}

function parseChapterRange(
	startRaw: string,
	endRaw: string,
): { start: number; end: number } | null {
	const startText = startRaw.trim();
	const endText = endRaw.trim();
	if (!/^\d+$/.test(startText) || !/^\d+$/.test(endText)) return null;
	const start = Number(startText);
	const end = Number(endText);
	if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > end) return null;
	return { start, end };
}

function NewTranslatedNovelForm({
	sourceWorkId,
	preferredLanguage,
	onCreated,
	onCancel,
}: {
	sourceWorkId: string;
	preferredLanguage: string | null;
	onCreated: (novel: TranslationTargetNovel) => void;
	onCancel: () => void;
}) {
	const [languagesState, setLanguagesState] = useState<Loadable<Language[]>>({
		status: "loading",
	});
	const [title, setTitle] = useState("");
	const [author, setAuthor] = useState("");
	const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	useEffect(() => {
		const controller = new AbortController();
		void readAllLanguagesLanguagesGet({ signal: controller.signal })
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status === 200) {
					setLanguagesState({ status: "ready", data: response.data });
				} else {
					setLanguagesState({
						status: "error",
						message: apiErrorMessage(response.data, "Could not load languages."),
					});
				}
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted) {
					setLanguagesState({ status: "error", message: requestErrorMessage(error) });
				}
			});
		return () => controller.abort();
	}, []);

	const languages = languagesState.status === "ready" ? languagesState.data : [];
	const matchedLanguage = findMatchingLanguageCode(languages, preferredLanguage);
	const effectiveLanguageCode =
		selectedLanguage ?? matchedLanguage ?? languages[0]?.languageCode ?? "";

	async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
		event.preventDefault();
		const trimmedTitle = title.trim();
		if (!trimmedTitle) {
			setSubmitError("Title is required.");
			return;
		}
		if (!effectiveLanguageCode) {
			setSubmitError("Language is required.");
			return;
		}
		setSubmitting(true);
		setSubmitError(null);
		try {
			const response = await createNovelNovelsPost({
				novelTitle: trimmedTitle,
				languageCode: effectiveLanguageCode,
				novelAuthor: author.trim() || null,
				novelDescription: null,
				novelType: NovelType.translation,
				novelVisibility: Visibility.NUMBER_0,
				sourceWorkId,
			});
			if (response.status !== 200) {
				setSubmitError(
					apiErrorMessage(response.data, "Could not create translated novel."),
				);
				return;
			}
			onCreated({
				novelId: response.data.novelId,
				novelTitle: response.data.novelTitle,
				languageCode: response.data.languageCode,
				novelType: response.data.novelType,
				novelVisibility: response.data.novelVisibility,
			});
		} catch (error: unknown) {
			setSubmitError(requestErrorMessage(error));
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<form
			onSubmit={(event) => {
				void handleSubmit(event);
			}}
			className="space-y-2 rounded-md border bg-background p-2.5"
		>
			<div className="space-y-2">
				<div className="space-y-1">
					<label htmlFor="new-translated-novel-title" className="text-xs font-medium">
						Title
					</label>
					<Input
						id="new-translated-novel-title"
						value={title}
						onChange={(event) => setTitle(event.target.value)}
						placeholder="Translated novel title"
						disabled={submitting}
						required
					/>
				</div>
				<div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
					<div className="space-y-1">
						<label
							htmlFor="new-translated-novel-language"
							className="text-xs font-medium"
						>
							Language
						</label>
						<select
							id="new-translated-novel-language"
							className="h-9 w-full rounded-md border bg-background px-2 text-sm"
							value={effectiveLanguageCode}
							onChange={(event) => setSelectedLanguage(event.target.value)}
							disabled={submitting || languagesState.status !== "ready"}
						>
							{languagesState.status === "loading" && (
								<option value="">Loading languages…</option>
							)}
							{languagesState.status === "error" && (
								<option value="">Languages unavailable</option>
							)}
							{languages.map((language) => (
								<option key={language.languageCode} value={language.languageCode}>
									{language.languageName} ({language.languageCode})
								</option>
							))}
						</select>
					</div>
					<div className="space-y-1">
						<label
							htmlFor="new-translated-novel-author"
							className="text-xs font-medium"
						>
							Author (optional)
						</label>
						<Input
							id="new-translated-novel-author"
							value={author}
							onChange={(event) => setAuthor(event.target.value)}
							placeholder="Author or translator"
							disabled={submitting}
						/>
					</div>
				</div>
			</div>
			{languagesState.status === "error" && (
				<p role="alert" className="text-xs text-destructive">
					{languagesState.message}
				</p>
			)}
			{submitError && (
				<p role="alert" className="text-xs text-destructive">
					{submitError}
				</p>
			)}
			<div className="flex items-center justify-end gap-2">
				<Button
					type="button"
					size="sm"
					variant="ghost"
					disabled={submitting}
					onClick={onCancel}
				>
					Cancel
				</Button>
				<Button
					type="submit"
					size="sm"
					disabled={
						submitting ||
						languagesState.status !== "ready" ||
						title.trim().length === 0 ||
						!effectiveLanguageCode
					}
				>
					{submitting ? "Creating…" : "Create novel"}
				</Button>
			</div>
		</form>
	);
}

export function TranslationReviewPanel({
	jobId,
	stages,
	sourceWorkId,
	currentChapterId,
	currentChapterContentId = null,
	editorScrollElement = null,
	onSelectChapter,
	onClose,
	onAccepted,
}: {
	jobId: string;
	stages: TranslationStageRead[];
	sourceWorkId: string | null;
	currentChapterId: string | null;
	currentChapterContentId?: string | null;
	editorScrollElement?: HTMLElement | null;
	onSelectChapter?: (chapterId: string) => void;
	onClose: () => void;
	onAccepted?: () => void;
}) {
	const [outputs, setOutputs] = useState<TranslationOutputsRead | null>(null);
	const [outputsError, setOutputsError] = useState<string | null>(null);
	const [outputsRevision, setOutputsRevision] = useState(0);

	const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
	const [manualChapter, setManualChapter] = useState<{
		forEditorChapterId: string | null;
		chapterId: string;
	} | null>(null);
	const [detailEntry, setDetailEntry] = useState<{
		key: string;
		state: Loadable<TranslationOutputChapterDetail>;
	} | null>(null);

	const [scrollSynced, setScrollSynced] = useState(true);
	const [showHeaderControls, setShowHeaderControls] = useState(false);
	const [showAcceptControls, setShowAcceptControls] = useState(false);
	const [showSnapshotSource, setShowSnapshotSource] = useState(false);
	const [showBulkAccept, setShowBulkAccept] = useState(false);

	const [createdNovels, setCreatedNovels] = useState<TranslationTargetNovel[]>([]);
	const [selectedTargetNovelId, setSelectedTargetNovelId] = useState<string | null>(null);
	const [showCreateNovel, setShowCreateNovel] = useState(false);

	const [scopeMode, setScopeMode] = useState<ScopeMode>("job");
	const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
	const [rangeStartInput, setRangeStartInput] = useState<string | null>(null);
	const [rangeEndInput, setRangeEndInput] = useState<string | null>(null);
	const [onExisting, setOnExisting] = useState<TranslationAcceptRequestOnExisting>(
		TranslationAcceptRequestOnExisting.skip,
	);

	const [accepting, setAccepting] = useState(false);
	const acceptingRef = useRef(false);
	const [acceptStatus, setAcceptStatus] = useState<string | null>(null);
	const [acceptError, setAcceptError] = useState<string | null>(null);

	const translatedScrollRef = useRef<HTMLDivElement | null>(null);
	const snapshotScrollRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		const controller = new AbortController();
		void listOutputsTranslationJobsJobIdOutputsGet(
			jobId,
			selectedStageId ? { stageId: selectedStageId } : undefined,
			{ signal: controller.signal },
		)
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status === 200) {
					setOutputs(response.data);
					setOutputsError(null);
				} else {
					setOutputsError(
						apiErrorMessage(
							response.data,
							"Could not load staged translation outputs.",
						),
					);
				}
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted) setOutputsError(requestErrorMessage(error));
			});
		return () => controller.abort();
	}, [jobId, selectedStageId, outputsRevision]);

	const stagedStages = useMemo(() => outputs?.stages ?? [], [outputs]);
	const activeStageId = selectedStageId ?? outputs?.selectedStageId ?? null;
	const items = useMemo(() => outputs?.items ?? [], [outputs]);

	const manualChapterId =
		manualChapter !== null && manualChapter.forEditorChapterId === currentChapterId
			? manualChapter.chapterId
			: null;

	const activeChapter = useMemo(() => {
		if (items.length === 0) return null;
		if (manualChapterId !== null) {
			return items.find((item) => item.chapterId === manualChapterId) ?? items[0];
		}
		if (currentChapterId !== null) {
			return items.find((item) => item.chapterId === currentChapterId) ?? items[0];
		}
		return items[0];
	}, [items, manualChapterId, currentChapterId]);

	const activeIndex = activeChapter
		? items.findIndex((item) => item.chapterId === activeChapter.chapterId)
		: -1;
	const activeChapterId = activeChapter?.chapterId ?? null;
	const currentChapterNotStaged =
		outputs !== null &&
		items.length > 0 &&
		currentChapterId !== null &&
		!items.some((item) => item.chapterId === currentChapterId);

	const detailKey = activeChapterId !== null ? `${activeStageId ?? ""}:${activeChapterId}` : null;

	useEffect(() => {
		if (activeChapterId === null || detailKey === null) return;
		const controller = new AbortController();
		void readOutputTranslationJobsJobIdOutputsChapterIdGet(
			jobId,
			activeChapterId,
			activeStageId ? { stageId: activeStageId } : undefined,
			{
				signal: controller.signal,
			},
		)
			.then((response) => {
				if (controller.signal.aborted) return;
				if (response.status === 200) {
					setDetailEntry({
						key: detailKey,
						state: { status: "ready", data: response.data },
					});
				} else {
					setDetailEntry({
						key: detailKey,
						state: {
							status: "error",
							message: apiErrorMessage(
								response.data,
								"Could not load chapter preview.",
							),
						},
					});
				}
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted) {
					setDetailEntry({
						key: detailKey,
						state: { status: "error", message: requestErrorMessage(error) },
					});
				}
			});
		return () => controller.abort();
	}, [jobId, activeChapterId, activeStageId, detailKey]);

	const detailState: Loadable<TranslationOutputChapterDetail> | null =
		detailKey === null
			? null
			: detailEntry && detailEntry.key === detailKey
				? detailEntry.state
				: { status: "loading" };

	const detailReady = detailState?.status === "ready";
	const matchesEditorChapter = activeChapterId !== null && activeChapterId === currentChapterId;
	const sourceEditedSinceSnapshot =
		detailReady &&
		matchesEditorChapter &&
		currentChapterContentId !== null &&
		detailState.data.sourceChapterContentId !== currentChapterContentId;

	useEffect(() => {
		if (!scrollSynced || !detailReady) return;
		const sourceEl = showSnapshotSource ? snapshotScrollRef.current : editorScrollElement;
		const targetEl = translatedScrollRef.current;
		if (!sourceEl || !targetEl) return;
		if (!showSnapshotSource && !matchesEditorChapter) return;

		let lockedOrigin: "source" | "target" | null = null;
		let unlockTimer: number | null = null;

		const sync = (from: HTMLElement, to: HTMLElement, origin: "source" | "target") => {
			if (lockedOrigin !== null && lockedOrigin !== origin) return;
			const maxFrom = from.scrollHeight - from.clientHeight;
			const maxTo = to.scrollHeight - to.clientHeight;
			if (maxFrom <= 0 || maxTo <= 0) return;
			lockedOrigin = origin;
			const nextTop = Math.round((from.scrollTop / maxFrom) * maxTo);
			if (Math.abs(to.scrollTop - nextTop) >= 1) {
				to.scrollTop = nextTop;
			}
			if (unlockTimer !== null) window.clearTimeout(unlockTimer);
			unlockTimer = window.setTimeout(() => {
				lockedOrigin = null;
			}, 80);
		};

		const onSourceScroll = () => sync(sourceEl, targetEl, "source");
		const onTargetScroll = () => sync(targetEl, sourceEl, "target");

		sourceEl.addEventListener("scroll", onSourceScroll, { passive: true });
		targetEl.addEventListener("scroll", onTargetScroll, { passive: true });
		return () => {
			if (unlockTimer !== null) window.clearTimeout(unlockTimer);
			sourceEl.removeEventListener("scroll", onSourceScroll);
			targetEl.removeEventListener("scroll", onTargetScroll);
		};
	}, [scrollSynced, showSnapshotSource, editorScrollElement, matchesEditorChapter, detailReady]);

	function selectChapter(chapterId: string) {
		setManualChapter({ forEditorChapterId: currentChapterId, chapterId });
		onSelectChapter?.(chapterId);
	}

	const targetNovels = useMemo(() => {
		const fromServer = outputs?.targetNovels ?? [];
		const seen = new Set(fromServer.map((novel) => novel.novelId));
		return [...fromServer, ...createdNovels.filter((novel) => !seen.has(novel.novelId))];
	}, [outputs, createdNovels]);

	const activeTargetNovelId = useMemo(() => {
		if (
			selectedTargetNovelId !== null &&
			targetNovels.some((novel) => novel.novelId === selectedTargetNovelId)
		) {
			return selectedTargetNovelId;
		}
		if (
			outputs?.lastTargetNovelId &&
			targetNovels.some((novel) => novel.novelId === outputs.lastTargetNovelId)
		) {
			return outputs.lastTargetNovelId;
		}
		return targetNovels[0]?.novelId ?? "";
	}, [selectedTargetNovelId, outputs, targetNovels]);

	const batches = useMemo(() => {
		const map = new Map<string, { batchId: string; batchNum: number; count: number }>();
		for (const item of items) {
			const existing = map.get(item.batchId);
			if (existing) {
				existing.count += 1;
			} else {
				map.set(item.batchId, {
					batchId: item.batchId,
					batchNum: item.batchNum,
					count: 1,
				});
			}
		}
		return Array.from(map.values()).sort((a, b) => a.batchNum - b.batchNum);
	}, [items]);

	const activeBatchId = useMemo(() => {
		if (selectedBatchId && batches.some((batch) => batch.batchId === selectedBatchId)) {
			return selectedBatchId;
		}
		if (activeChapter && batches.some((batch) => batch.batchId === activeChapter.batchId)) {
			return activeChapter.batchId;
		}
		return batches[0]?.batchId ?? "";
	}, [selectedBatchId, activeChapter, batches]);

	const activeBatch = batches.find((batch) => batch.batchId === activeBatchId) ?? null;

	const chapterBounds = useMemo(() => {
		if (items.length === 0) return { min: 0, max: 0 };
		let min = items[0].chapterNum;
		let max = items[0].chapterNum;
		for (const item of items) {
			if (item.chapterNum < min) min = item.chapterNum;
			if (item.chapterNum > max) max = item.chapterNum;
		}
		return { min, max };
	}, [items]);

	const rangeStartValue = rangeStartInput ?? String(chapterBounds.min);
	const rangeEndValue = rangeEndInput ?? String(chapterBounds.max);
	const parsedRange = parseChapterRange(rangeStartValue, rangeEndValue);

	const preferredLanguage = useMemo(() => findTargetLanguage(stages), [stages]);

	async function runAccept(scope: TranslationAcceptScope) {
		if (acceptingRef.current || !activeTargetNovelId) return;
		acceptingRef.current = true;
		setAccepting(true);
		setAcceptError(null);
		setAcceptStatus(null);
		const payload: TranslationAcceptRequest = {
			targetNovelId: activeTargetNovelId,
			scope,
			...(activeStageId ? { stageId: activeStageId } : {}),
			onExisting,
		};
		try {
			const response = await acceptOutputsTranslationJobsJobIdAcceptPost(jobId, payload);
			if (response.status !== 200) {
				setAcceptError(
					apiErrorMessage(response.data, "Could not accept translation outputs."),
				);
				return;
			}
			const result = response.data;
			setAcceptStatus(
				`Created ${result.createdChapters}, updated ${result.updatedChapters}, skipped ${result.skippedChapters}.`,
			);
			setSelectedTargetNovelId(result.targetNovelId);
			setOutputsRevision((value) => value + 1);
			onAccepted?.();
		} catch (error: unknown) {
			setAcceptError(requestErrorMessage(error));
		} finally {
			acceptingRef.current = false;
			setAccepting(false);
		}
	}

	function handleBulkAccept() {
		if (scopeMode === "job") {
			void runAccept({ mode: TranslationAcceptJobScopeMode.job });
			return;
		}
		if (scopeMode === "batch") {
			if (!activeBatchId) return;
			void runAccept({
				mode: TranslationAcceptBatchScopeMode.batch,
				batchId: activeBatchId,
			});
			return;
		}
		if (!parsedRange) return;
		void runAccept({
			mode: TranslationAcceptRangeScopeMode.range,
			startChapterNum: parsedRange.start,
			endChapterNum: parsedRange.end,
		});
	}

	const bulkAcceptDisabled =
		accepting ||
		!activeTargetNovelId ||
		items.length === 0 ||
		(scopeMode === "batch" && !activeBatchId) ||
		(scopeMode === "range" && parsedRange === null);

	const activeAcceptedNovels = activeChapter?.acceptedNovelIds ?? [];
	const activeAcceptedInTarget =
		activeTargetNovelId !== "" && activeAcceptedNovels.includes(activeTargetNovelId);

	return (
		<section
			aria-label={`Review job ${jobId.slice(0, 8)}`}
			className="flex h-full min-h-0 flex-col"
		>
			<header className="shrink-0 border-b px-2 py-1.5">
				<div className="flex items-center gap-1">
					<Button
						type="button"
						size="sm"
						variant="ghost"
						className="h-7 px-1.5"
						onClick={onClose}
					>
						<ArrowLeft className="size-3.5" />
						Jobs
					</Button>
					<h2 className="mr-auto truncate text-xs font-medium text-muted-foreground">
						Job {jobId.slice(0, 8)} · Review
						{activeChapter ? ` · Ch. ${activeChapter.chapterNum}` : ""}
					</h2>
					{activeAcceptedInTarget && (
						<span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
							Accepted
						</span>
					)}
					<Button
						type="button"
						size="icon-sm"
						variant={scrollSynced ? "secondary" : "ghost"}
						aria-label={scrollSynced ? "Detach scroll sync" : "Sync scroll with source"}
						aria-pressed={scrollSynced}
						title={
							scrollSynced
								? "Scroll locked with source (click to detach)"
								: "Scroll detached (click to sync with source)"
						}
						onClick={() => setScrollSynced((value) => !value)}
					>
						{scrollSynced ? (
							<Link2 className="size-3.5" />
						) : (
							<Unlink2 className="size-3.5" />
						)}
					</Button>
					<Button
						type="button"
						size="icon-sm"
						variant={showHeaderControls ? "secondary" : "ghost"}
						aria-label="Toggle review controls"
						aria-expanded={showHeaderControls}
						title={showHeaderControls ? "Hide review controls" : "Show review controls"}
						onClick={() => setShowHeaderControls((value) => !value)}
					>
						{showHeaderControls ? (
							<ChevronUp className="size-3.5" />
						) : (
							<ChevronDown className="size-3.5" />
						)}
					</Button>
				</div>

				{outputs && activeChapter && showHeaderControls && (
					<div className="mt-2 space-y-1.5 border-t pt-2">
						{stagedStages.length > 1 && (
							<div className="flex items-center gap-2">
								<label
									htmlFor="review-staged-stage-select"
									className="text-xs text-muted-foreground"
								>
									Stage
								</label>
								<select
									id="review-staged-stage-select"
									aria-label="Staged stage"
									className="h-8 flex-1 rounded-md border bg-background px-2 text-xs"
									value={activeStageId ?? ""}
									onChange={(event) => {
										setSelectedStageId(event.target.value);
										setAcceptStatus(null);
										setAcceptError(null);
									}}
								>
									{stagedStages.map((stage) => (
										<option key={stage.stageId} value={stage.stageId}>
											Stage {stage.stageNum}:{" "}
											{stage.action.replaceAll("_", " ")} (
											{stage.chapterCount})
										</option>
									))}
								</select>
							</div>
						)}

						<div className="flex items-center gap-1.5">
							<label htmlFor="review-staged-chapter-select" className="sr-only">
								Staged chapter
							</label>
							<select
								id="review-staged-chapter-select"
								className="h-8 min-w-0 flex-1 rounded-md border bg-background px-2 text-xs"
								value={activeChapter.chapterId}
								onChange={(event) => selectChapter(event.target.value)}
							>
								{items.map((item) => {
									const acceptedIds = item.acceptedNovelIds ?? [];
									const isAccepted =
										activeTargetNovelId !== ""
											? acceptedIds.includes(activeTargetNovelId)
											: acceptedIds.length > 0;
									const titlePart = item.chapterTitle
										? `: ${item.chapterTitle}`
										: "";
									const acceptedLabel = isAccepted
										? " (accepted)"
										: acceptedIds.length > 0
											? " (accepted in another novel)"
											: "";
									return (
										<option key={item.chapterId} value={item.chapterId}>
											Ch. {item.chapterNum}
											{titlePart}
											{acceptedLabel}
										</option>
									);
								})}
							</select>
							<Button
								type="button"
								size="icon-sm"
								variant="outline"
								aria-label="Previous staged chapter"
								disabled={activeIndex <= 0}
								onClick={() => {
									if (activeIndex > 0) {
										selectChapter(items[activeIndex - 1].chapterId);
									}
								}}
							>
								<ChevronLeft className="size-4" />
							</Button>
							<Button
								type="button"
								size="icon-sm"
								variant="outline"
								aria-label="Next staged chapter"
								disabled={activeIndex < 0 || activeIndex >= items.length - 1}
								onClick={() => {
									if (activeIndex >= 0 && activeIndex < items.length - 1) {
										selectChapter(items[activeIndex + 1].chapterId);
									}
								}}
							>
								<ChevronRight className="size-4" />
							</Button>
						</div>

						<div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
							<span className="tabular-nums">
								{activeIndex + 1} / {items.length} · Batch{" "}
								{activeChapter.batchNum + 1}
							</span>
							<Button
								type="button"
								size="sm"
								variant={showSnapshotSource ? "secondary" : "ghost"}
								className="h-7 px-2 text-xs"
								aria-pressed={showSnapshotSource}
								onClick={() => setShowSnapshotSource((value) => !value)}
							>
								<FileText className="size-3.5" />
								{showSnapshotSource
									? "Hide source snapshot"
									: "Show source snapshot"}
							</Button>
						</div>
					</div>
				)}

				{outputs && activeChapter && currentChapterNotStaged && (
					<p className="mt-1 px-1 text-xs text-muted-foreground">
						Current editor chapter is not staged in this job; starting at Ch.{" "}
						{items[0].chapterNum}.
					</p>
				)}
				{outputs && activeChapter && sourceEditedSinceSnapshot && !showSnapshotSource && (
					<p className="mt-1 px-1 text-xs text-amber-700 dark:text-amber-300">
						Source chapter changed since this job ran. Expand controls to inspect the
						snapshotted text.
					</p>
				)}
			</header>

			<div className="flex min-h-0 flex-1 flex-col overflow-hidden">
				{!outputs && !outputsError && (
					<p role="status" className="p-4 text-sm text-muted-foreground">
						Loading staged outputs…
					</p>
				)}

				{outputsError && (
					<div className="space-y-2 p-4">
						<p role="alert" className="text-sm text-destructive">
							{outputsError}
						</p>
						{!outputs && (
							<Button
								size="sm"
								variant="outline"
								onClick={() => {
									setOutputsError(null);
									setOutputsRevision((value) => value + 1);
								}}
							>
								Retry loading
							</Button>
						)}
					</div>
				)}

				{outputs && items.length === 0 && (
					<div className="p-4">
						<p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
							No staged translated chapters are available for this job yet.
						</p>
					</div>
				)}

				{outputs && activeChapter && detailState?.status === "loading" && (
					<p role="status" className="p-4 text-center text-sm text-muted-foreground">
						Loading chapter preview…
					</p>
				)}

				{outputs && activeChapter && detailState?.status === "error" && (
					<p role="alert" className="p-4 text-sm text-destructive">
						{detailState.message}
					</p>
				)}

				{outputs && activeChapter && detailState?.status === "ready" && (
					<div className="flex min-h-0 flex-1 flex-col divide-y overflow-hidden">
						{showSnapshotSource && (
							<div className="flex min-h-0 flex-1 flex-col overflow-hidden">
								<div className="shrink-0 bg-muted/30 px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
									Source snapshot
								</div>
								<div
									ref={snapshotScrollRef}
									data-testid="review-source-scroll"
									className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-2.5 font-reading text-base leading-relaxed whitespace-pre-wrap contain-content"
								>
									{detailState.data.sourceText}
								</div>
							</div>
						)}
						<div className="flex min-h-0 flex-1 flex-col overflow-hidden">
							{showSnapshotSource && (
								<div className="shrink-0 bg-muted/30 px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
									Translated
								</div>
							)}
							<div
								ref={translatedScrollRef}
								data-testid="review-translated-scroll"
								className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 text-base leading-relaxed contain-content"
							>
								<div className="mb-3 flex items-baseline justify-between gap-2 border-b pb-2 text-xs text-muted-foreground">
									<span className="font-medium text-foreground">
										Ch. {activeChapter.chapterNum}
										{activeChapter.chapterTitle
											? `: ${activeChapter.chapterTitle}`
											: ""}
									</span>
									<span className="shrink-0 tabular-nums">
										Batch {activeChapter.batchNum + 1} · {activeIndex + 1} /{" "}
										{items.length}
									</span>
								</div>
								<div className="font-reading whitespace-pre-wrap">
									{detailState.data.translatedText}
								</div>
								<div className="mt-6 flex items-center justify-between gap-2 border-t pt-3">
									<Button
										type="button"
										size="sm"
										variant="ghost"
										disabled={activeIndex <= 0}
										onClick={() => {
											if (activeIndex > 0) {
												selectChapter(items[activeIndex - 1].chapterId);
											}
										}}
									>
										<ChevronLeft className="size-3.5" />
										Prev
									</Button>
									<Button
										type="button"
										size="sm"
										variant="outline"
										onClick={() => setShowAcceptControls(true)}
									>
										Accept…
									</Button>
									<Button
										type="button"
										size="sm"
										variant="ghost"
										disabled={
											activeIndex < 0 || activeIndex >= items.length - 1
										}
										onClick={() => {
											if (
												activeIndex >= 0 &&
												activeIndex < items.length - 1
											) {
												selectChapter(items[activeIndex + 1].chapterId);
											}
										}}
									>
										Next
										<ChevronRight className="size-3.5" />
									</Button>
								</div>
							</div>
						</div>
					</div>
				)}
			</div>

			{outputs && activeChapter && (
				<footer
					aria-label="Accept translation outputs"
					className="shrink-0 border-t bg-muted/20 px-2 py-1.5"
				>
					<div className="flex items-center justify-between gap-2">
						<span className="truncate text-xs text-muted-foreground">
							{acceptStatus ?? "Accept outputs"}
						</span>
						<Button
							type="button"
							size="icon-sm"
							variant={showAcceptControls ? "secondary" : "ghost"}
							aria-label="Toggle accept controls"
							aria-expanded={showAcceptControls}
							title={
								showAcceptControls ? "Hide accept controls" : "Show accept controls"
							}
							onClick={() => setShowAcceptControls((value) => !value)}
						>
							{showAcceptControls ? (
								<ChevronDown className="size-3.5" />
							) : (
								<ChevronUp className="size-3.5" />
							)}
						</Button>
					</div>

					{showAcceptControls && (
						<div className="mt-2 space-y-2 border-t pt-2">
							<div className="flex flex-wrap items-end gap-1.5">
								<div className="min-w-36 flex-1 space-y-1">
									<label
										htmlFor="review-target-novel-select"
										className="text-xs font-medium"
									>
										Target novel
									</label>
									<select
										id="review-target-novel-select"
										className="h-8 w-full rounded-md border bg-background px-2 text-xs"
										value={activeTargetNovelId}
										onChange={(event) =>
											setSelectedTargetNovelId(event.target.value)
										}
										disabled={accepting || targetNovels.length === 0}
									>
										{targetNovels.length === 0 && (
											<option value="">No target novels yet</option>
										)}
										{targetNovels.map((novel) => (
											<option key={novel.novelId} value={novel.novelId}>
												{novel.novelTitle} ({novel.languageCode})
											</option>
										))}
									</select>
								</div>
								<Button
									type="button"
									size="sm"
									variant="outline"
									aria-label="New translated novel"
									disabled={accepting || !sourceWorkId}
									onClick={() => setShowCreateNovel((open) => !open)}
								>
									<Plus className="size-3.5" />
									New
								</Button>
								<Button
									type="button"
									size="sm"
									disabled={accepting || !activeTargetNovelId}
									onClick={() => {
										void runAccept({
											mode: TranslationAcceptRangeScopeMode.range,
											startChapterNum: activeChapter.chapterNum,
											endChapterNum: activeChapter.chapterNum,
										});
									}}
								>
									Accept Ch. {activeChapter.chapterNum}
								</Button>
							</div>

							{showCreateNovel && sourceWorkId && (
								<NewTranslatedNovelForm
									sourceWorkId={sourceWorkId}
									preferredLanguage={preferredLanguage}
									onCreated={(novel) => {
										setCreatedNovels((prev) => [...prev, novel]);
										setSelectedTargetNovelId(novel.novelId);
										setShowCreateNovel(false);
										setAcceptError(null);
										setAcceptStatus(`Created "${novel.novelTitle}".`);
									}}
									onCancel={() => setShowCreateNovel(false)}
								/>
							)}

							<div>
								<Button
									type="button"
									size="sm"
									variant="ghost"
									className="h-7 px-1.5 text-xs text-muted-foreground"
									aria-expanded={showBulkAccept}
									onClick={() => setShowBulkAccept((open) => !open)}
								>
									{showBulkAccept ? (
										<ChevronUp className="size-3.5" />
									) : (
										<ChevronDown className="size-3.5" />
									)}
									Bulk accept options
								</Button>

								{showBulkAccept && (
									<div className="mt-2 space-y-2 rounded-md border bg-background p-2.5">
										<div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
											<div className="space-y-1">
												<label
													htmlFor="review-accept-scope-select"
													className="text-xs font-medium"
												>
													Scope
												</label>
												<select
													id="review-accept-scope-select"
													className="h-8 w-full rounded-md border bg-background px-2 text-xs"
													value={scopeMode}
													onChange={(event) =>
														setScopeMode(
															parseScopeMode(event.target.value),
														)
													}
													disabled={accepting}
												>
													<option value="job">
														Whole job ({items.length} staged)
													</option>
													<option value="batch">
														Batch{" "}
														{activeBatch ? activeBatch.batchNum + 1 : 1}
													</option>
													<option value="range">Range (start–end)</option>
												</select>
											</div>

											<div className="space-y-1">
												<label
													htmlFor="review-on-existing-select"
													className="text-xs font-medium"
												>
													Existing chapters
												</label>
												<select
													id="review-on-existing-select"
													className="h-8 w-full rounded-md border bg-background px-2 text-xs"
													value={onExisting}
													onChange={(event) =>
														setOnExisting(
															parseOnExisting(event.target.value),
														)
													}
													disabled={accepting}
												>
													<option
														value={
															TranslationAcceptRequestOnExisting.skip
														}
													>
														Skip existing
													</option>
													<option
														value={
															TranslationAcceptRequestOnExisting.overwrite
														}
													>
														Overwrite as new version
													</option>
												</select>
											</div>
										</div>

										{scopeMode === "batch" && (
											<div className="space-y-1">
												<label
													htmlFor="review-accept-batch-select"
													className="text-xs font-medium"
												>
													Batch
												</label>
												<select
													id="review-accept-batch-select"
													className="h-8 w-full rounded-md border bg-background px-2 text-xs"
													value={activeBatchId}
													onChange={(event) =>
														setSelectedBatchId(event.target.value)
													}
													disabled={accepting}
												>
													{batches.map((batch) => (
														<option
															key={batch.batchId}
															value={batch.batchId}
														>
															Batch {batch.batchNum + 1} (
															{batch.count} ch.)
														</option>
													))}
												</select>
											</div>
										)}

										{scopeMode === "range" && (
											<div className="grid grid-cols-2 gap-2">
												<div className="space-y-1">
													<label
														htmlFor="review-range-start"
														className="text-xs font-medium"
													>
														Start chapter
													</label>
													<Input
														id="review-range-start"
														type="number"
														min={0}
														value={rangeStartValue}
														onChange={(event) =>
															setRangeStartInput(event.target.value)
														}
														disabled={accepting}
													/>
												</div>
												<div className="space-y-1">
													<label
														htmlFor="review-range-end"
														className="text-xs font-medium"
													>
														End chapter
													</label>
													<Input
														id="review-range-end"
														type="number"
														min={0}
														value={rangeEndValue}
														onChange={(event) =>
															setRangeEndInput(event.target.value)
														}
														disabled={accepting}
													/>
												</div>
											</div>
										)}

										{scopeMode === "range" && parsedRange === null && (
											<p role="alert" className="text-xs text-destructive">
												Enter a valid non-negative chapter range where start
												is less than or equal to end.
											</p>
										)}

										<Button
											type="button"
											size="sm"
											variant="secondary"
											className="w-full"
											disabled={bulkAcceptDisabled}
											onClick={handleBulkAccept}
										>
											{accepting ? "Accepting…" : "Accept chapters"}
										</Button>
									</div>
								)}
							</div>

							{acceptStatus && (
								<p role="status" aria-live="polite" className="text-xs">
									{acceptStatus}
								</p>
							)}
							{acceptError && (
								<p role="alert" className="text-xs text-destructive">
									{acceptError}
								</p>
							)}
						</div>
					)}
				</footer>
			)}
		</section>
	);
}
