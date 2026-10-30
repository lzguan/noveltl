import { useCallback, useRef, useState } from "react";
import {
	listJobsTranslationJobsGet,
	startTranslationJobsJobIdStartPost,
	resumeAllTranslationJobsJobIdResumeAllPost,
	cancelAllTranslationJobsJobIdCancelAllPost,
	retryAllTranslationJobsJobIdRetryAllPost,
	startBatchTranslationJobsJobIdBatchesBatchIdStartPost,
	resumeBatchTranslationJobsJobIdBatchesBatchIdResumePost,
	cancelTranslationJobsJobIdBatchesBatchIdCancelPost,
	retryTranslationJobsJobIdBatchesBatchIdRetryPost,
} from "@/api/endpoints/translations/translations";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { CreateTranslationDialog } from "./CreateTranslationDialog";
import { BatchDialog, JobCard, Pagination } from "./TranslationJobViewer";
import type { Control, ViewerControls } from "./TranslationJobViewer";
import { useTranslationRead } from "./useTranslationRead";

const jobControls = {
	Start: startTranslationJobsJobIdStartPost,
	Resume: resumeAllTranslationJobsJobIdResumeAllPost,
	Cancel: cancelAllTranslationJobsJobIdCancelAllPost,
	Retry: retryAllTranslationJobsJobIdRetryAllPost,
};
const batchControls = {
	Start: startBatchTranslationJobsJobIdBatchesBatchIdStartPost,
	Resume: resumeBatchTranslationJobsJobIdBatchesBatchIdResumePost,
	Cancel: cancelTranslationJobsJobIdBatchesBatchIdCancelPost,
	Retry: retryTranslationJobsJobIdBatchesBatchIdRetryPost,
};
function JobList({
	novelId,
	page,
	revision,
	onPage,
	onDetails,
	...controls
}: ViewerControls & {
	novelId: string;
	page: number;
	revision: number;
	onPage: (page: number) => void;
	onDetails: (id: string) => void;
}) {
	const load = useCallback(
		async (signal: AbortSignal) => {
			const response = await listJobsTranslationJobsGet(
				{ novelId, offset: page * 5, limit: 5 },
				{ signal },
			);
			if (response.status !== 200)
				throw new Error(apiErrorMessage(response.data, "Could not load translation jobs."));
			return response.data;
		},
		[novelId, page],
	);
	const { data, error, refreshing, refresh } = useTranslationRead(load, revision);
	return (
		<>
			<Button size="sm" variant="outline" disabled={refreshing} onClick={refresh}>
				Refresh jobs
			</Button>
			{!data && !error && <p role="status">Loading translation jobs…</p>}
			{error && (
				<p role="alert">
					{error}
					{data && " Showing the last loaded progress."}
				</p>
			)}
			{data && (
				<>
					{data.items.length === 0 && (
						<p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
							{data.total ? "No jobs on this page." : "No translation jobs yet."}
						</p>
					)}
					{data.items.map((job) => (
						<JobCard
							key={job.jobId}
							job={job}
							onDetails={() => onDetails(job.jobId)}
							{...controls}
						/>
					))}
					<Pagination page={page} total={data.total} onPage={onPage} />
				</>
			)}
		</>
	);
}
export function TranslationsPanel({
	novelId,
	chapterNumbers,
}: {
	novelId: string;
	chapterNumbers: number[];
}) {
	const [creating, setCreating] = useState(false);
	const [details, setDetails] = useState<string>();
	const [notice, setNotice] = useState("");
	const [pending, setPending] = useState(false);
	const pendingRef = useRef(false);
	const [page, setPage] = useState(0);
	const [revision, setRevision] = useState(0);
	async function control(jobId: string, operation: Control, batchId?: string) {
		if (pendingRef.current) return;
		pendingRef.current = true;
		setPending(true);
		setNotice(`${operation} requested…`);
		try {
			const response =
				batchId === undefined
					? await jobControls[operation](jobId)
					: await batchControls[operation](jobId, batchId);
			if (response.status !== 200)
				throw new Error(
					apiErrorMessage(
						response.data,
						`Could not ${operation.toLowerCase()} translation work.`,
					),
				);
			const result = response.data;
			setNotice(
				result.dispatchFailedTaskIds?.length
					? `${result.dispatchFailedTaskIds.length} tasks could not be queued. Use Resume to try dispatching them again.`
					: `${operation}: ${result.affectedBatchIds?.length ?? 0} batches affected, ${result.dispatchedTaskIds?.length ?? 0} tasks queued.`,
			);
		} catch (error: unknown) {
			setNotice(requestErrorMessage(error));
		} finally {
			setRevision((value) => value + 1);
			pendingRef.current = false;
			setPending(false);
		}
	}
	return (
		<div className="h-full overflow-y-auto p-3 space-y-4">
			<div className="flex justify-between items-center">
				<h2 className="font-semibold">Translations</h2>
				<Button size="sm" onClick={() => setCreating(true)}>
					+ Create job
				</Button>
			</div>
			<p role="status" aria-live="polite" className="text-xs">
				{notice}
			</p>
			<JobList
				key={`${novelId}:${page}`}
				novelId={novelId}
				page={page}
				revision={revision}
				onPage={setPage}
				onDetails={setDetails}
				pending={pending}
				onControl={control}
			/>
			{details && (
				<BatchDialog
					key={details}
					jobId={details}
					revision={revision}
					notice={notice}
					onClose={() => setDetails(undefined)}
					pending={pending}
					onControl={control}
				/>
			)}
			{creating && (
				<CreateTranslationDialog
					novelId={novelId}
					chapterNumbers={chapterNumbers}
					onClose={() => setCreating(false)}
					onCreate={(jobId) => {
						setCreating(false);
						setDetails(jobId);
						setRevision((value) => value + 1);
						setNotice("Job saved. Use Start when you are ready to translate.");
					}}
				/>
			)}
		</div>
	);
}
