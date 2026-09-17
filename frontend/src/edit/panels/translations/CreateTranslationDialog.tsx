import { useState } from "react";
import type { IChangeEvent } from "@rjsf/core";
import { Form } from "@rjsf/shadcn";
import validator from "@rjsf/validator-ajv8";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogDescription,
} from "@/components/ui/dialog";
import { actions } from "./prototype";
import type { Job, Stage } from "./prototype";

const selectClass = "h-9 w-full rounded-md border bg-background px-2 text-sm";
export function CreateTranslationDialog({
	onClose,
	onCreate,
}: {
	onClose: () => void;
	onCreate: (job: Job) => void;
}) {
	const [memoryGroup, setMemoryGroup] = useState("");
	const [stages, setStages] = useState<Stage[]>([]);
	const [selected, setSelected] = useState("");
	const [configuring, setConfiguring] = useState<string | null>(null);
	const [pending, setPending] = useState<{ index: number; group?: string } | null>(null);
	const [start, setStart] = useState("1");
	const [end, setEnd] = useState("500");
	const [batchSize, setBatchSize] = useState("100");
	const inputs =
		stages.at(-1)?.action.outputs ?? (memoryGroup ? ["Chapter", "Memories"] : ["Chapter"]);
	const available = actions.filter(
		(action) =>
			(stages.length > 0 || action.first) &&
			action.inputs.every((input) => inputs.includes(input)),
	);
	const validRange =
		[start, end, batchSize].every(
			(value) => value.trim() !== "" && Number.isSafeInteger(Number(value)),
		) &&
		Number(start) >= 0 &&
		Number(end) >= Number(start) &&
		Number(batchSize) > 0 &&
		Number(end) - Number(start) < 10000;
	function addStage() {
		const action = available.find((item) => item.id === selected);
		if (!action || stages.length === 5) return;
		const config = Object.fromEntries(
			Object.entries(action.schema.properties ?? {}).flatMap(([name, field]) =>
				typeof field === "object" && field.default !== undefined
					? [[name, field.default]]
					: [],
			),
		);
		const stage = { id: crypto.randomUUID(), action, config };
		setStages([...stages, stage]);
		setSelected("");
	}
	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Create translation job</DialogTitle>
					<DialogDescription>
						Choose source chapters and build a pipeline of up to five stages.
					</DialogDescription>
				</DialogHeader>
				<div className="grid grid-cols-3 gap-3">
					<label className="space-y-1 text-sm">
						From chapter
						<Input
							type="number"
							min={0}
							value={start}
							onChange={(event) => setStart(event.target.value)}
						/>
					</label>
					<label className="space-y-1 text-sm">
						To chapter (inclusive)
						<Input
							type="number"
							min={0}
							value={end}
							onChange={(event) => setEnd(event.target.value)}
						/>
					</label>
					<label className="space-y-1 text-sm">
						Chapters per batch
						<Input
							type="number"
							min={1}
							value={batchSize}
							onChange={(event) => setBatchSize(event.target.value)}
						/>
					</label>
				</div>
				{!validRange && (
					<p role="alert" className="text-sm text-destructive">
						Enter a valid range of up to 10,000 chapters and a positive batch size.
					</p>
				)}
				<label className="space-y-2 text-sm">
					Memory group
					<select
						className={selectClass}
						value={memoryGroup}
						onChange={(event) => {
							const group = event.target.value;
							if (!group && stages[0]?.action.inputs.includes("Memories"))
								setPending({ index: 0, group });
							else {
								setMemoryGroup(group);
								setSelected("");
							}
						}}
					>
						<option value="">None</option>
						<option>Main glossary</option>
						<option>Reviewed memories</option>
					</select>
				</label>
				<p className="text-xs text-muted-foreground">
					Initial inputs: Chapter{memoryGroup && " + Memories"}
				</p>
				<div className="space-y-3">
					<h3 className="font-medium">
						Stages <span className="text-muted-foreground">{stages.length} / 5</span>
					</h3>
					{stages.length === 0 && (
						<p className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">
							Add your first stage below.
						</p>
					)}
					{stages.map((stage, index) => (
						<section key={stage.id} className="rounded-lg border p-4 space-y-3">
							<div className="flex flex-wrap items-center gap-2">
								<h4 className="mr-auto font-medium">
									{index + 1}. {stage.action.label}
								</h4>
								<Button
									size="sm"
									variant="outline"
									onClick={() =>
										setConfiguring(configuring === stage.id ? null : stage.id)
									}
								>
									{configuring === stage.id ? "Cancel changes" : "Configure"}
								</Button>
								<Button
									size="sm"
									variant="ghost"
									aria-label={`Remove stage ${index + 1} and following stages`}
									onClick={() => setPending({ index })}
								>
									Remove
								</Button>
							</div>
							<p className="text-xs text-muted-foreground">
								{stage.action.inputs.join(" + ")} →{" "}
								{stage.action.outputs.join(" + ")}
							</p>
							<p className="text-sm">
								{[
									stage.config.model,
									stage.config.target_language,
									stage.config.instructions ? "Custom instructions" : null,
								]
									.filter((value) => typeof value === "string")
									.join(" · ") || "No configuration required"}
							</p>
							{configuring === stage.id && (
								<Form
									schema={stage.action.schema}
									validator={validator}
									formData={stage.config}
									uiSchema={{
										instructions: { "ui:widget": "textarea" },
										"ui:submitButtonOptions": {
											submitText: "Save configuration",
										},
									}}
									onSubmit={({
										formData,
									}: IChangeEvent<Record<string, unknown>>) => {
										if (formData)
											setStages(
												stages.map((item) =>
													item.id === stage.id
														? { ...item, config: formData }
														: item,
												),
											);
										setConfiguring(null);
									}}
								/>
							)}
						</section>
					))}
					{pending && (
						<div
							role="alert"
							className="rounded-lg border border-destructive/40 p-3 space-y-2 text-sm"
						>
							<p>
								Remove stages {pending.index + 1}–{stages.length}
								{pending.group !== undefined ? " to remove the memory group" : ""}?
							</p>
							<Button
								size="sm"
								variant="destructive"
								onClick={() => {
									setStages(stages.slice(0, pending.index));
									if (pending.group !== undefined) setMemoryGroup(pending.group);
									setConfiguring(null);
									setSelected("");
									setPending(null);
								}}
							>
								Remove stages
							</Button>{" "}
							<Button size="sm" variant="outline" onClick={() => setPending(null)}>
								Keep stages
							</Button>
						</div>
					)}
					{stages.length < 5 && (
						<div className="flex items-end gap-2">
							<label className="flex-1 space-y-1 text-sm">
								Add stage
								<select
									className={selectClass}
									value={selected}
									onChange={(event) => setSelected(event.target.value)}
								>
									<option value="">Select compatible action</option>
									{available.map((action) => (
										<option key={action.id} value={action.id}>
											{action.label}
										</option>
									))}
								</select>
							</label>
							<Button
								disabled={!selected || pending !== null || configuring !== null}
								onClick={addStage}
							>
								Add stage
							</Button>
						</div>
					)}
				</div>
				<div className="flex justify-end gap-2">
					<Button variant="outline" onClick={onClose}>
						Cancel
					</Button>
					<Button
						disabled={
							!validRange ||
							stages.length === 0 ||
							configuring !== null ||
							pending !== null
						}
						onClick={() =>
							onCreate({
								id: crypto.randomUUID(),
								title: "New translation job",
								start: Number(start),
								end: Number(end),
								memoryGroup,
								stages,
								batches: Array.from(
									{
										length: Math.ceil(
											(Number(end) - Number(start) + 1) / Number(batchSize),
										),
									},
									(_, index) => ({
										id: index + 1,
										completed: 0,
										state: "Not started",
									}),
								),
							})
						}
					>
						Create job
					</Button>
				</div>
			</DialogContent>
		</Dialog>
	);
}
