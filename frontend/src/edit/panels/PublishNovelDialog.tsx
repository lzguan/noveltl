import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
	AlertCircleIcon,
	CheckCircle2Icon,
	ExternalLinkIcon,
	InfoIcon,
	LoaderCircleIcon,
	RefreshCwIcon,
	RotateCcwIcon,
	UploadIcon,
} from "lucide-react";

import {
	readNovelPublishJobNovelsNovelIdPublishJobsJobIdGet,
	readNovelPublishStatusNovelsNovelIdPublishStatusGet,
	readPublishingTargetsPublishingTargetsGet,
	startNovelPublishNovelsNovelIdPublishPost,
} from "@/api/endpoints/publishing/publishing";
import {
	PublishJobStatus,
	PublishMode,
	type NovelPublishStatus,
	type PublishJobRead,
	type PublishingTargetRead,
	type StartPublishRequest,
} from "@/api/models";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { cn } from "@/lib/utils";
import { AppRoutes } from "@/routes";

const POLL_INTERVAL_MS = 1500;

const MODE_OPTIONS: readonly {
	value: PublishMode;
	label: string;
	description: string;
}[] = [
	{
		value: PublishMode.outdated,
		label: "Outdated & new",
		description: "Sync only chapters that are new or changed since the last publish.",
	},
	{
		value: PublishMode.range,
		label: "Chapter range",
		description: "Sync an inclusive range of chapter numbers.",
	},
	{
		value: PublishMode.all,
		label: "All chapters",
		description: "Re-sync every chapter in this novel to the Reader.",
	},
];

type ParsedChapterNum = { ok: true; value: number } | { ok: false };

function parseNonNegativeChapter(raw: string): ParsedChapterNum {
	const trimmed = raw.trim();
	if (!/^\d+$/.test(trimmed)) return { ok: false };
	const parsed = Number.parseInt(trimmed, 10);
	return Number.isSafeInteger(parsed) && parsed >= 0
		? { ok: true, value: parsed }
		: { ok: false };
}

function isJobActive(job: PublishJobRead | null): boolean {
	return (
		job !== null &&
		(job.status === PublishJobStatus.pending || job.status === PublishJobStatus.processing)
	);
}

function jobStatusLabel(status: PublishJobStatus): string {
	switch (status) {
		case PublishJobStatus.pending:
			return "Pending";
		case PublishJobStatus.processing:
			return "Processing";
		case PublishJobStatus.completed:
			return "Completed";
		case PublishJobStatus.failed:
			return "Failed";
	}
}

function jobStatusVariant(
	status: PublishJobStatus,
): "default" | "secondary" | "destructive" | "outline" {
	switch (status) {
		case PublishJobStatus.completed:
			return "default";
		case PublishJobStatus.failed:
			return "destructive";
		case PublishJobStatus.processing:
			return "secondary";
		case PublishJobStatus.pending:
			return "outline";
	}
}

function usePublishForm() {
	const [mode, setMode] = useState<PublishMode>(PublishMode.outdated);
	const [startChapter, setStartChapter] = useState("");
	const [endChapter, setEndChapter] = useState("");
	const [includeNovelMetadata, setIncludeNovelMetadata] = useState(true);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function startSubmit() {
		setSubmitting(true);
		setError(null);
	}

	function submitSuccess() {
		setSubmitting(false);
		setError(null);
	}

	function submitFailure(message: string) {
		setSubmitting(false);
		setError(message);
	}

	return {
		mode,
		setMode,
		startChapter,
		setStartChapter,
		endChapter,
		setEndChapter,
		includeNovelMetadata,
		setIncludeNovelMetadata,
		submitting,
		error,
		startSubmit,
		submitSuccess,
		submitFailure,
	};
}

type FetchResult<T> = { ok: true; data: T } | { ok: false; error: string };

async function requestNovelPublishStatus(
	novelId: string,
	targetId: string,
	signal: AbortSignal,
): Promise<FetchResult<NovelPublishStatus>> {
	try {
		const resp = await readNovelPublishStatusNovelsNovelIdPublishStatusGet(
			novelId,
			{ targetId },
			{ signal },
		);
		if (resp.status !== 200) {
			return {
				ok: false,
				error: apiErrorMessage(resp.data, "Could not load publish status."),
			};
		}
		return { ok: true, data: resp.data };
	} catch (err: unknown) {
		return { ok: false, error: requestErrorMessage(err) };
	}
}

async function requestPublishingTargets(
	signal: AbortSignal,
): Promise<FetchResult<PublishingTargetRead[]>> {
	try {
		const resp = await readPublishingTargetsPublishingTargetsGet({ signal });
		if (resp.status !== 200) {
			return {
				ok: false,
				error: apiErrorMessage(resp.data, "Could not load publishing targets."),
			};
		}
		return { ok: true, data: resp.data };
	} catch (err: unknown) {
		return { ok: false, error: requestErrorMessage(err) };
	}
}

function PublishTargetPanel({
	novelId,
	target,
	onClose,
}: {
	novelId: string;
	target: PublishingTargetRead;
	onClose: () => void;
}) {
	const [status, setStatus] = useState<NovelPublishStatus | null>(null);
	const [statusError, setStatusError] = useState<string | null>(null);
	const [statusLoading, setStatusLoading] = useState(true);
	const statusControllerRef = useRef<AbortController | null>(null);

	const [trackedJob, setTrackedJob] = useState<PublishJobRead | null>(null);
	const [pollError, setPollError] = useState<string | null>(null);

	const form = usePublishForm();

	const applyStatusResult = useCallback((result: FetchResult<NovelPublishStatus>) => {
		if (!result.ok) {
			setStatusError(result.error);
		} else {
			setStatus(result.data);
			setStatusError(null);
			if (result.data.activeJob !== null) {
				setTrackedJob(result.data.activeJob);
			}
		}
		setStatusLoading(false);
	}, []);

	const refreshStatus = useCallback(() => {
		statusControllerRef.current?.abort();
		const controller = new AbortController();
		statusControllerRef.current = controller;
		setStatusLoading(true);
		void requestNovelPublishStatus(novelId, target.targetId, controller.signal).then(
			(result) => {
				if (!controller.signal.aborted) applyStatusResult(result);
			},
		);
	}, [applyStatusResult, novelId, target.targetId]);

	useEffect(() => {
		const controller = new AbortController();
		statusControllerRef.current = controller;
		void requestNovelPublishStatus(novelId, target.targetId, controller.signal).then(
			(result) => {
				if (!controller.signal.aborted) applyStatusResult(result);
			},
		);
		return () => {
			statusControllerRef.current?.abort();
		};
	}, [applyStatusResult, novelId, target.targetId]);

	const pollingJobId = isJobActive(trackedJob) ? (trackedJob?.jobId ?? null) : null;

	useEffect(() => {
		if (pollingJobId === null) return;

		let cancelled = false;
		let timeoutId: number | null = null;
		let controller: AbortController | null = null;

		const poll = () => {
			controller = new AbortController();
			const activeController = controller;

			readNovelPublishJobNovelsNovelIdPublishJobsJobIdGet(novelId, pollingJobId, {
				signal: activeController.signal,
			})
				.then((resp) => {
					if (cancelled) return;
					if (resp.status !== 200) {
						setPollError(apiErrorMessage(resp.data, "Could not refresh job progress."));
						timeoutId = window.setTimeout(poll, POLL_INTERVAL_MS);
						return;
					}
					setTrackedJob(resp.data);
					setPollError(null);
					if (resp.data.status === PublishJobStatus.completed) {
						refreshStatus();
						return;
					}
					if (resp.data.status === PublishJobStatus.failed) {
						return;
					}
					timeoutId = window.setTimeout(poll, POLL_INTERVAL_MS);
				})
				.catch((err: unknown) => {
					if (cancelled || activeController.signal.aborted) return;
					setPollError(requestErrorMessage(err));
					timeoutId = window.setTimeout(poll, POLL_INTERVAL_MS);
				});
		};

		timeoutId = window.setTimeout(poll, POLL_INTERVAL_MS);

		return () => {
			cancelled = true;
			if (timeoutId !== null) window.clearTimeout(timeoutId);
			controller?.abort();
		};
	}, [novelId, pollingJobId, refreshStatus]);

	const parsedStart = parseNonNegativeChapter(form.startChapter);
	const parsedEnd = parseNonNegativeChapter(form.endChapter);

	let rangeError: string | null = null;
	if (form.mode === PublishMode.range) {
		if (!form.startChapter.trim() || !form.endChapter.trim()) {
			rangeError = "Enter both start and end chapter numbers.";
		} else if (!parsedStart.ok || !parsedEnd.ok) {
			rangeError = "Chapter numbers must be whole integers greater than or equal to 0.";
		} else if (parsedStart.value > parsedEnd.value) {
			rangeError = "Start chapter must be less than or equal to end chapter.";
		}
	}

	const jobRunning = isJobActive(trackedJob);
	const publicUrl = trackedJob?.publicUrl ?? status?.publicUrl ?? null;

	async function handleStartPublish() {
		if (form.submitting || jobRunning) return;
		if (
			form.mode === PublishMode.range &&
			(rangeError !== null || !parsedStart.ok || !parsedEnd.ok)
		) {
			return;
		}

		const payload: StartPublishRequest = {
			targetId: target.targetId,
			mode: form.mode,
			includeNovelMetadata: form.includeNovelMetadata,
			...(form.mode === PublishMode.range && parsedStart.ok && parsedEnd.ok
				? {
						startChapter: parsedStart.value,
						endChapter: parsedEnd.value,
					}
				: {}),
		};

		form.startSubmit();
		setPollError(null);
		try {
			const resp = await startNovelPublishNovelsNovelIdPublishPost(novelId, payload);
			if (resp.status !== 202) {
				form.submitFailure(apiErrorMessage(resp.data, "Could not start publish job."));
				return;
			}
			form.submitSuccess();
			setTrackedJob(resp.data);
			if (resp.data.status === PublishJobStatus.completed) {
				refreshStatus();
			}
		} catch (err: unknown) {
			form.submitFailure(requestErrorMessage(err));
		}
	}

	const startDisabled =
		form.submitting || jobRunning || (form.mode === PublishMode.range && rangeError !== null);

	return (
		<div className="flex flex-col gap-4">
			<section className="space-y-2.5 rounded-lg border bg-muted/20 p-3">
				<div className="flex flex-wrap items-center justify-between gap-2">
					<span className="text-xs font-medium text-muted-foreground">Reader status</span>
					<div className="flex items-center gap-2">
						{publicUrl && (
							<a
								href={publicUrl}
								target="_blank"
								rel="noopener noreferrer"
								className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-4 hover:underline"
							>
								View on Reader ↗
							</a>
						)}
						<Button
							type="button"
							variant="ghost"
							size="xs"
							disabled={statusLoading}
							onClick={refreshStatus}
						>
							<RefreshCwIcon
								className={cn("size-3", statusLoading && "animate-spin")}
							/>
							Refresh status
						</Button>
					</div>
				</div>

				{statusLoading && status === null && (
					<div className="flex gap-2">
						<Skeleton className="h-6 w-20" />
						<Skeleton className="h-6 w-24" />
						<Skeleton className="h-6 w-24" />
					</div>
				)}

				{statusError !== null && (
					<Alert variant="destructive">
						<AlertCircleIcon />
						<AlertDescription>{statusError}</AlertDescription>
					</Alert>
				)}

				{status !== null && (
					<div className="space-y-2">
						<div className="flex flex-wrap items-center gap-1.5">
							<Badge variant="default">New: {status.newCount}</Badge>
							<Badge variant="secondary">Outdated: {status.outdatedCount}</Badge>
							<Badge variant="outline">Up to date: {status.upToDateCount}</Badge>
						</div>
						<p className="text-xs text-muted-foreground">
							{status.existsOnReader
								? `${status.studioChapterCount} chapter(s) in Studio · ${status.readerChapterCount} on Reader.`
								: `Not yet published on ${target.name} (${status.studioChapterCount} chapter(s) in Studio).`}
						</p>
						{status.readerOnlyCount > 0 && (
							<p className="flex items-start gap-1.5 text-xs text-muted-foreground">
								<InfoIcon className="mt-0.5 size-3.5 shrink-0" />
								<span>
									{status.readerOnlyCount} chapter(s) exist on Reader but not in
									Studio; remove via Reader Admin
								</span>
							</p>
						)}
					</div>
				)}
			</section>

			{trackedJob !== null && (
				<section
					aria-label="Publish job progress"
					className="space-y-2.5 rounded-lg border bg-card p-3"
				>
					<div className="flex flex-wrap items-center justify-between gap-2">
						<div className="flex items-center gap-2">
							<Badge variant={jobStatusVariant(trackedJob.status)}>
								{jobRunning && <LoaderCircleIcon className="size-3 animate-spin" />}
								{trackedJob.status === PublishJobStatus.completed && (
									<CheckCircle2Icon className="size-3" />
								)}
								{jobStatusLabel(trackedJob.status)}
							</Badge>
							<span className="text-xs tabular-nums text-muted-foreground">
								{trackedJob.syncedChapters} / {trackedJob.totalChapters} chapters
							</span>
						</div>

						{trackedJob.status === PublishJobStatus.completed && publicUrl && (
							<a
								href={publicUrl}
								target="_blank"
								rel="noopener noreferrer"
								className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-4 hover:underline"
							>
								View on Reader ↗
								<ExternalLinkIcon className="size-3" />
							</a>
						)}
					</div>

					<progress
						aria-label="Publish progress"
						className="h-2 w-full accent-primary"
						value={trackedJob.syncedChapters}
						max={trackedJob.totalChapters || 1}
					/>

					{pollError !== null && (
						<p role="alert" className="text-xs text-destructive">
							{pollError}
						</p>
					)}

					{trackedJob.status === PublishJobStatus.failed && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertDescription className="flex flex-wrap items-center justify-between gap-2">
								<span>{trackedJob.errorMessage ?? "Publish job failed."}</span>
								<Button
									type="button"
									variant="outline"
									size="xs"
									disabled={form.submitting}
									onClick={() => void handleStartPublish()}
								>
									<RotateCcwIcon data-icon="inline-start" />
									Retry
								</Button>
							</AlertDescription>
						</Alert>
					)}
				</section>
			)}

			<FieldGroup className="gap-3">
				<div className="space-y-1.5">
					<span className="text-xs font-medium">Publish mode</span>
					<div
						role="radiogroup"
						aria-label="Publish mode"
						className="flex flex-col gap-1.5"
					>
						{MODE_OPTIONS.map((option) => {
							const checked = form.mode === option.value;
							return (
								<button
									key={option.value}
									type="button"
									role="radio"
									aria-checked={checked}
									disabled={form.submitting || jobRunning}
									className={cn(
										"flex cursor-pointer flex-col rounded-md border px-3 py-2 text-left text-xs disabled:cursor-not-allowed disabled:opacity-50",
										checked
											? "border-primary bg-accent/60 text-foreground"
											: "border-border text-muted-foreground hover:bg-accent/30 hover:text-foreground",
									)}
									onClick={() => form.setMode(option.value)}
								>
									<span className="font-medium text-foreground">
										{option.label}
									</span>
									<span className="text-muted-foreground">
										{option.description}
									</span>
								</button>
							);
						})}
					</div>
				</div>

				{form.mode === PublishMode.range && (
					<div className="space-y-2">
						<div className="grid grid-cols-2 gap-2">
							<Field>
								<FieldLabel htmlFor="publish-start-chapter">
									Start chapter
								</FieldLabel>
								<Input
									id="publish-start-chapter"
									type="number"
									min={0}
									step={1}
									inputMode="numeric"
									placeholder="1"
									value={form.startChapter}
									disabled={form.submitting || jobRunning}
									onChange={(e) => form.setStartChapter(e.target.value)}
								/>
							</Field>
							<Field>
								<FieldLabel htmlFor="publish-end-chapter">End chapter</FieldLabel>
								<Input
									id="publish-end-chapter"
									type="number"
									min={0}
									step={1}
									inputMode="numeric"
									placeholder="10"
									value={form.endChapter}
									disabled={form.submitting || jobRunning}
									onChange={(e) => form.setEndChapter(e.target.value)}
								/>
							</Field>
						</div>
						{rangeError !== null && (
							<p role="alert" className="text-xs text-destructive">
								{rangeError}
							</p>
						)}
					</div>
				)}

				<div className="flex items-center gap-2 pt-1">
					<Checkbox
						id="publish-include-metadata"
						checked={form.includeNovelMetadata}
						disabled={form.submitting || jobRunning}
						onCheckedChange={(checked) =>
							form.setIncludeNovelMetadata(checked === true)
						}
					/>
					<Label htmlFor="publish-include-metadata" className="text-xs font-normal">
						Include novel metadata (title, author, description)
					</Label>
				</div>
			</FieldGroup>

			{form.error !== null && (
				<Alert variant="destructive">
					<AlertCircleIcon />
					<AlertDescription>{form.error}</AlertDescription>
				</Alert>
			)}

			<DialogFooter>
				<Button type="button" variant="outline" onClick={onClose}>
					Close
				</Button>
				<Button
					type="button"
					disabled={startDisabled}
					onClick={() => void handleStartPublish()}
				>
					<UploadIcon data-icon="inline-start" />
					{form.submitting
						? "Starting..."
						: jobRunning
							? "Publishing..."
							: "Start publish"}
				</Button>
			</DialogFooter>
		</div>
	);
}

export function PublishNovelDialog({
	novelId,
	novelTitle,
	onClose,
}: {
	novelId: string;
	novelTitle: string;
	onClose: () => void;
}) {
	const [targets, setTargets] = useState<PublishingTargetRead[]>([]);
	const [targetsError, setTargetsError] = useState<string | null>(null);
	const [loadingTargets, setLoadingTargets] = useState(true);
	const targetsControllerRef = useRef<AbortController | null>(null);
	const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);

	const applyTargetsResult = useCallback((result: FetchResult<PublishingTargetRead[]>) => {
		if (!result.ok) {
			setTargetsError(result.error);
		} else {
			setTargets(result.data);
			setTargetsError(null);
		}
		setLoadingTargets(false);
	}, []);

	const retryLoadTargets = useCallback(() => {
		targetsControllerRef.current?.abort();
		const controller = new AbortController();
		targetsControllerRef.current = controller;
		setLoadingTargets(true);
		void requestPublishingTargets(controller.signal).then((result) => {
			if (!controller.signal.aborted) applyTargetsResult(result);
		});
	}, [applyTargetsResult]);

	useEffect(() => {
		const controller = new AbortController();
		targetsControllerRef.current = controller;
		void requestPublishingTargets(controller.signal).then((result) => {
			if (!controller.signal.aborted) applyTargetsResult(result);
		});
		return () => {
			targetsControllerRef.current?.abort();
		};
	}, [applyTargetsResult]);

	const activeTarget =
		targets.find((target) => target.targetId === selectedTargetId) ?? targets[0] ?? null;

	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
				<DialogHeader>
					<DialogTitle>Publish novel</DialogTitle>
					<DialogDescription>
						Sync &ldquo;{novelTitle}&rdquo; and its chapters to a connected Reader
						instance.
					</DialogDescription>
				</DialogHeader>

				{loadingTargets && (
					<div className="space-y-3 py-2">
						<Skeleton className="h-9 w-full" />
						<Skeleton className="h-24 w-full" />
					</div>
				)}

				{!loadingTargets && targetsError !== null && (
					<div className="space-y-4">
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertDescription className="flex flex-wrap items-center justify-between gap-2">
								<span>{targetsError}</span>
								<Button
									type="button"
									variant="outline"
									size="xs"
									onClick={retryLoadTargets}
								>
									Retry
								</Button>
							</AlertDescription>
						</Alert>
						<DialogFooter>
							<Button type="button" variant="outline" onClick={onClose}>
								Close
							</Button>
						</DialogFooter>
					</div>
				)}

				{!loadingTargets && targetsError === null && targets.length === 0 && (
					<div className="space-y-4">
						<div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
							<p className="mb-3">
								You don&apos;t have access to any Reader publishing targets yet.
							</p>
							<Button asChild size="sm">
								<Link to={AppRoutes.SETTINGS} onClick={onClose}>
									Configure a Reader target in Settings
								</Link>
							</Button>
						</div>
						<DialogFooter>
							<Button type="button" variant="outline" onClick={onClose}>
								Close
							</Button>
						</DialogFooter>
					</div>
				)}

				{!loadingTargets && targetsError === null && activeTarget !== null && (
					<div className="flex flex-col gap-4">
						<Field>
							<FieldLabel htmlFor="publish-target-select">Target Reader</FieldLabel>
							<Select
								value={activeTarget.targetId}
								onValueChange={setSelectedTargetId}
							>
								<SelectTrigger id="publish-target-select" className="w-full">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{targets.map((target) => (
										<SelectItem key={target.targetId} value={target.targetId}>
											{target.name}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</Field>

						<PublishTargetPanel
							key={activeTarget.targetId}
							novelId={novelId}
							target={activeTarget}
							onClose={onClose}
						/>
					</div>
				)}
			</DialogContent>
		</Dialog>
	);
}
