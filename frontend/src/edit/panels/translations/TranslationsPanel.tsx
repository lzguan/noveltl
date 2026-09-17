import { useState } from "react";
import { Info, LoaderCircle, TriangleAlert } from "lucide-react";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogDescription,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { CreateTranslationDialog } from "./CreateTranslationDialog";
import { controls, demoJobs, eligible } from "./prototype";
import type { Batch, Control, Job } from "./prototype";

function Progress({ completed, total }: { completed: number; total: number }) {
	const percent = total ? Math.round((completed / total) * 100) : 0;
	return (
		<div className="flex items-center gap-2">
			<progress
				aria-label="Completed pipeline stages"
				className="h-2 w-full accent-primary"
				value={completed}
				max={total || 1}
			/>
			<span className="text-xs tabular-nums text-muted-foreground">{percent}%</span>
		</div>
	);
}
function Controls({
	batches,
	onControl,
}: {
	batches: Batch[];
	onControl: (control: Control) => void;
}) {
	return (
		<div className="flex flex-wrap gap-1">
			{controls.map((control) => {
				const enabled = batches.some((batch) => eligible(batch, control));
				return (
					<Button
						key={control}
						size="sm"
						variant="outline"
						disabled={!enabled}
						title={
							enabled
								? `${control} eligible batches`
								: `No batches available to ${control.toLowerCase()}`
						}
						onClick={() => onControl(control)}
					>
						{control}
					</Button>
				);
			})}
		</div>
	);
}
function JobCard({
	notice,
	job,
	onControl,
}: {
	notice: string;
	job: Job;
	onControl: (control: Control, batchId?: number) => void;
}) {
	const [detailsOpen, setDetailsOpen] = useState(false);
	const [page, setPage] = useState(0);
	const completed = job.batches.reduce((total, batch) => total + batch.completed, 0);
	const running = job.batches.filter((batch) => batch.state === "Running").length;
	const failed = job.batches.filter((batch) => batch.state === "Failed").length;
	const complete = job.batches.every((batch) => batch.state === "Complete");
	const state = complete
		? "Complete"
		: running
			? "Running"
			: failed
				? "Failed"
				: job.batches.some((batch) => batch.state === "Interrupted")
					? "Interrupted"
					: job.batches.some((batch) => batch.state === "Cancelled")
						? "Cancelled"
						: "Not started";
	const pageCount = Math.ceil(job.batches.length / 5);
	return (
		<Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
			<article className="rounded-lg border bg-card p-3 space-y-3">
				<div className="flex items-center gap-2">
					<h3 className="mr-auto font-medium">{job.title}</h3>
					<span className="text-xs">{state}</span>
					{running > 0 && (
						<LoaderCircle aria-label="Running" className="size-3.5 animate-spin" />
					)}
					{failed > 0 && (
						<TriangleAlert
							aria-label="Some batches failed"
							className="size-4 text-amber-600"
						/>
					)}
					<DialogTrigger asChild>
						<Button
							size="icon-sm"
							variant="ghost"
							aria-label={`Show details for ${job.title}`}
						>
							<Info />
						</Button>
					</DialogTrigger>
				</div>
				<p className="text-xs text-muted-foreground">
					Chapters {job.start}–{job.end} · {job.stages.length} stages ·{" "}
					{job.batches.length} batches
				</p>
				<Progress completed={completed} total={job.stages.length * job.batches.length} />
				<p className="text-xs text-muted-foreground">
					{job.batches.filter((batch) => batch.state === "Complete").length} complete ·{" "}
					{running} running · {failed} failed
				</p>
				<Controls batches={job.batches} onControl={onControl} />
				{complete && job.stages.at(-1)?.action.outputs.includes("Chapter") && (
					<div>
						<Button variant="outline" disabled>
							Create novel from results
						</Button>
						<p className="mt-1 text-xs text-muted-foreground">
							Conversion will be available after backend integration.
						</p>
					</div>
				)}
				<DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
					<DialogHeader>
						<DialogTitle>{job.title} · Batches</DialogTitle>
						<DialogDescription>
							Progress and controls for each batch in this translation job.
						</DialogDescription>
					</DialogHeader>
					<p role="status" aria-live="polite" className="text-xs">
						{notice}
					</p>
					<p className="text-xs leading-relaxed">
						{job.stages.map((stage) => stage.action.label).join(" → ")}
					</p>
					{job.memoryGroup && (
						<p className="text-xs text-muted-foreground">
							Memory group: {job.memoryGroup}
						</p>
					)}
					{job.batches.slice(page * 5, (page + 1) * 5).map((batch) => (
						<section key={batch.id} className="rounded-md bg-muted/40 p-3 space-y-2">
							<div className="flex justify-between gap-2 text-sm">
								<h4 className="font-medium">Batch {batch.id}</h4>
								<span>{batch.state}</span>
							</div>
							<Progress completed={batch.completed} total={job.stages.length} />
							<p className="text-xs text-muted-foreground">
								{batch.completed} / {job.stages.length} stages complete
								{batch.state !== "Complete" &&
									` · ${job.stages[batch.completed]?.action.label}`}
							</p>
							{batch.state === "Running" && (
								<p className="text-xs">Processing current stage…</p>
							)}
							{batch.error && (
								<details className="text-xs text-destructive">
									<summary className="cursor-pointer">Show error</summary>
									<p className="pt-2">{batch.error}</p>
								</details>
							)}
							<Controls
								batches={[batch]}
								onControl={(control) => onControl(control, batch.id)}
							/>
						</section>
					))}
					{pageCount > 1 && (
						<div className="flex items-center justify-between">
							<Button
								size="sm"
								variant="ghost"
								disabled={page === 0}
								onClick={() => setPage(page - 1)}
							>
								Previous
							</Button>
							<span className="text-xs">
								{page + 1} / {pageCount}
							</span>
							<Button
								size="sm"
								variant="ghost"
								disabled={page + 1 >= pageCount}
								onClick={() => setPage(page + 1)}
							>
								Next
							</Button>
						</div>
					)}
				</DialogContent>
			</article>
		</Dialog>
	);
}
export function TranslationsPanel() {
	const [jobs, setJobs] = useState(demoJobs);
	const [creating, setCreating] = useState(false);
	const [notice, setNotice] = useState("");
	const [failDispatch, setFailDispatch] = useState(false);
	const [page, setPage] = useState(0);
	function control(jobId: string, operation: Control, batchId?: number) {
		const failedDispatch = failDispatch && operation !== "Cancel";
		setJobs((current) =>
			current.map((job) =>
				job.id !== jobId
					? job
					: {
							...job,
							batches: job.batches.map((batch) => {
								if (
									(batchId !== undefined && batch.id !== batchId) ||
									!eligible(batch, operation)
								)
									return batch;
								return {
									...batch,
									state:
										operation === "Cancel"
											? "Cancelled"
											: failedDispatch
												? "Interrupted"
												: "Running",
									error: undefined,
								};
							}),
						},
			),
		);
		setNotice(
			failedDispatch
				? "Could not queue work. The affected batches can be resumed."
				: `${operation} applied to eligible ${batchId === undefined ? "batches" : "batch"}.`,
		);
		if (operation !== "Cancel") setFailDispatch(false);
	}
	function advance() {
		setJobs((current) =>
			current.map((job) => ({
				...job,
				batches: job.batches.map((batch) =>
					batch.state !== "Running"
						? batch
						: {
								...batch,
								completed: batch.completed + 1,
								state:
									batch.completed + 1 === job.stages.length
										? "Complete"
										: "Running",
							},
				),
			})),
		);
	}
	const pageCount = Math.max(1, Math.ceil(jobs.length / 5));
	return (
		<div className="h-full overflow-y-auto p-3 space-y-4">
			<div className="flex justify-between items-center">
				<h2 className="font-semibold">Translations</h2>
				<Button size="sm" onClick={() => setCreating(true)}>
					+ Create job
				</Button>
			</div>
			<details className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
				<summary className="cursor-pointer">
					Prototype · sample data, no jobs submitted
				</summary>
				<div className="mt-3 flex flex-wrap gap-2">
					<Button size="sm" variant="outline" onClick={advance}>
						Advance running stages
					</Button>
					<Button
						size="sm"
						variant="outline"
						onClick={() => {
							setJobs(demoJobs());
							setPage(0);
							setNotice("");
						}}
					>
						Reset samples
					</Button>
					<Button
						size="sm"
						variant="outline"
						onClick={() => {
							setJobs([]);
							setPage(0);
							setNotice("");
						}}
					>
						Show empty list
					</Button>
					<label className="flex items-center gap-2">
						<input
							type="checkbox"
							checked={failDispatch}
							onChange={(event) => setFailDispatch(event.target.checked)}
						/>
						Fail next dispatch
					</label>
				</div>
			</details>
			<p role="status" aria-live="polite" className="text-xs">
				{notice}
			</p>
			{jobs.length === 0 && (
				<div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
					No translation jobs yet. Create a job to build your first pipeline.
				</div>
			)}
			{jobs.slice(page * 5, (page + 1) * 5).map((job) => (
				<JobCard
					notice={notice}
					key={job.id}
					job={job}
					onControl={(operation, batchId) => control(job.id, operation, batchId)}
				/>
			))}
			{pageCount > 1 && (
				<div className="flex justify-between items-center">
					<Button
						size="sm"
						variant="outline"
						disabled={page === 0}
						onClick={() => setPage(page - 1)}
					>
						Previous
					</Button>
					<span className="text-xs">
						{page + 1} / {pageCount}
					</span>
					<Button
						size="sm"
						variant="outline"
						disabled={page + 1 >= pageCount}
						onClick={() => setPage(page + 1)}
					>
						Next
					</Button>
				</div>
			)}
			{creating && (
				<CreateTranslationDialog
					onClose={() => setCreating(false)}
					onCreate={(job) => {
						setJobs((current) => [job, ...current]);
						setPage(0);
						setCreating(false);
						setNotice("Job created. Select Start when ready.");
					}}
				/>
			)}
		</div>
	);
}
