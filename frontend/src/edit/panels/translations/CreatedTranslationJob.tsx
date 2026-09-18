import { useEffect, useState } from "react";
import { readTranslationJobsJobIdGet } from "@/api/endpoints/translations/translations";
import type { TranslationJobRead } from "@/api/models";
import { Button } from "@/components/ui/button";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import type { Loadable } from "@/lib/loadable";

/** Real jobs are deliberately separate from the prototype's simulated controls. */
export function CreatedTranslationJob({ jobId }: { jobId: string }) {
	const [job, setJob] = useState<Loadable<TranslationJobRead>>({ status: "loading" });
	const [attempt, setAttempt] = useState(0);
	useEffect(() => {
		const controller = new AbortController();
		void readTranslationJobsJobIdGet(jobId, { signal: controller.signal })
			.then((response) => {
				if (!controller.signal.aborted)
					setJob(
						response.status === 200
							? { status: "ready", data: response.data }
							: {
									status: "error",
									message: apiErrorMessage(
										response.data,
										"Could not load the created job.",
									),
								},
					);
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted)
					setJob({ status: "error", message: requestErrorMessage(error) });
			});
		return () => controller.abort();
	}, [jobId, attempt]);
	return (
		<article className="rounded-lg border p-3 space-y-2">
			<h3 className="font-medium">Created translation job</h3>
			<p className="break-all text-xs text-muted-foreground">{jobId}</p>
			{job.status === "loading" && <p role="status">Loading job details…</p>}
			{job.status === "error" && (
				<p role="alert">
					Job was created, but its details could not be loaded: {job.message}
				</p>
			)}
			{job.status === "ready" && (
				<>
					<p className="text-sm">
						{job.data.stages.length} stages · {job.data.batches.length} batches ·{" "}
						{job.data.tasks.filter((task) => task.status === "complete").length} /{" "}
						{job.data.tasks.length} tasks complete
					</p>
					{job.data.tasks.length === 0 && (
						<p className="text-sm">No source chapters were selected by the server.</p>
					)}
					{job.data.tasks.some((task) => task.failedAt !== null) && (
						<p className="text-sm text-destructive">Some tasks have failed.</p>
					)}
				</>
			)}
			<p className="text-xs text-muted-foreground">
				Read-only until live job controls are connected. Creation does not start
				translation.
			</p>
			<Button
				size="sm"
				variant="outline"
				disabled={job.status === "loading"}
				onClick={() => {
					setJob({ status: "loading" });
					setAttempt((value) => value + 1);
				}}
			>
				Reload details
			</Button>
		</article>
	);
}
