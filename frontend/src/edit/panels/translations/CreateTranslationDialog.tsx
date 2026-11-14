import { useEffect, useRef, useState } from "react";
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
import { readUI } from "./schemaUi";
import { StageConfigForm } from "./StageConfigForm";
import { PipelineDiagram } from "./pipeline-diagram/PipelineDiagram";
import type { RJSFSchema } from "@rjsf/utils";
import { MemoryType, PluginName } from "@/api/models";
import type {
	TranslationActionMetadata,
	TranslationJobCreateRequestInputs,
	TranslationPipelineCheck,
} from "@/api/models";
import {
	checkTranslationJobsCheckPost,
	createTranslationJobsPost,
	listActionsTranslationJobsActionsGet,
} from "@/api/endpoints/translations/translations";
import { useMemoryGroupsContext } from "@/memory/context/MemoryGroupsContext";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import type { Loadable } from "@/lib/loadable";

type Props = {
	novelId: string;
	chapterNumbers: number[];
	onClose: () => void;
	onCreate: (jobId: string) => void;
};
type Action = { id: string; label: string; schema: RJSFSchema };
type Stage = { id: string; action: Action; config: Record<string, unknown> };

export function CreateTranslationDialog(props: Props) {
	const [catalog, setCatalog] = useState<Loadable<TranslationActionMetadata[]>>({
		status: "loading",
	});
	const [attempt, setAttempt] = useState(0);
	useEffect(() => {
		const controller = new AbortController();
		void listActionsTranslationJobsActionsGet({ signal: controller.signal })
			.then((response) => {
				if (!controller.signal.aborted)
					setCatalog(
						response.status === 200
							? { status: "ready", data: response.data.actions }
							: {
									status: "error",
									message: apiErrorMessage(
										response.data,
										"Could not load translation actions.",
									),
								},
					);
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted)
					setCatalog({ status: "error", message: requestErrorMessage(error) });
			});
		return () => controller.abort();
	}, [attempt]);
	if (catalog.status === "ready")
		return (
			<CreateTranslationForm
				{...props}
				actions={catalog.data.map((action) => ({
					id: action.name,
					label: action.label,
					schema: action.configSchema,
				}))}
			/>
		);
	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) props.onClose();
			}}
		>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Create translation job</DialogTitle>
					<DialogDescription>Loading available translation actions.</DialogDescription>
				</DialogHeader>
				{catalog.status === "error" ? (
					<>
						<p role="alert">{catalog.message}</p>
						<Button
							onClick={() => {
								setCatalog({ status: "loading" });
								setAttempt((value) => value + 1);
							}}
						>
							Retry loading
						</Button>
					</>
				) : (
					<p role="status">Loading actions…</p>
				)}
			</DialogContent>
		</Dialog>
	);
}

function formSchema(action: Action): RJSFSchema {
	return {
		...action.schema,
		properties: Object.fromEntries(
			Object.entries(action.schema.properties ?? {}).map(([name, field]) => {
				if (typeof field === "boolean") return [name, field];
				const words = name.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replaceAll("_", " ");
				const title =
					field.title ?? words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
				const numeric = field.anyOf?.find(
					(branch) =>
						typeof branch === "object" &&
						(branch.type === "number" ||
							branch.type === "integer" ||
							branch.type === "array"),
				);
				if (
					["number", "filter-checklist"].includes(readUI(field).control ?? "") &&
					field.anyOf?.length === 2 &&
					typeof numeric === "object" &&
					field.anyOf.some(
						(branch) => typeof branch === "object" && branch.type === "null",
					)
				) {
					const normalized: RJSFSchema = {
						...field,
						...numeric,
						title,
						type: [
							numeric.type === "integer"
								? "integer"
								: numeric.type === "array"
									? "array"
									: "number",
							"null",
						],
						description:
							field.description ??
							(numeric.type === "array"
								? "All values are included unless a selection is specified."
								: "Leave blank to use the provider default."),
					};
					delete normalized.anyOf;
					return [name, normalized];
				}
				return [name, { ...field, title }];
			}),
		),
	};
}

/** null means unrestricted; an explicit empty list intentionally matches nothing. */
function MemoryFilter<T extends string>({
	title,
	allLabel,
	choices,
	value,
	onChange,
}: {
	title: string;
	allLabel: string;
	choices: T[];
	value: T[] | null;
	onChange: (value: T[] | null) => void;
}) {
	return (
		<fieldset className="space-y-2 rounded-md border p-3">
			<legend className="px-1 text-sm font-medium">{title}</legend>
			<label className="flex items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={value === null}
					onChange={(event) => onChange(event.target.checked ? null : [])}
				/>
				{allLabel}
			</label>
			{value !== null && (
				<>
					<p className="text-xs text-muted-foreground">
						Selecting none excludes all memories.
					</p>
					{choices.map((choice) => (
						<label key={choice} className="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								checked={value.includes(choice)}
								onChange={(event) =>
									onChange(
										event.target.checked
											? [...value, choice]
											: value.filter((item) => item !== choice),
									)
								}
							/>
							{choice}
						</label>
					))}
				</>
			)}
		</fieldset>
	);
}

const selectClass = "h-9 w-full rounded-md border bg-background px-2 text-sm";
function CreateTranslationForm({
	novelId,
	chapterNumbers,
	onClose,
	onCreate,
	actions,
}: Props & { actions: Action[] }) {
	const { groups, reloadGroups } = useMemoryGroupsContext();
	const [submitting, setSubmitting] = useState(false);
	const submittingRef = useRef(false);
	const [error, setError] = useState<string | null>(null);
	const [stageErrors, setStageErrors] = useState<Record<number, string>>({});
	const [memoryGroup, setMemoryGroup] = useState("");
	const [stages, setStages] = useState<Stage[]>([]);
	const [selected, setSelected] = useState("");
	const [configuring, setConfiguring] = useState<string | null>(null);
	const [excludeCurrentChapter, setExcludeCurrentChapter] = useState(true);
	const [pluginNames, setPluginNames] = useState<PluginName[] | null>(null);
	const [memoryTypes, setMemoryTypes] = useState<MemoryType[] | null>(null);
	const [advanced, setAdvanced] = useState(false);
	const [pending, setPending] = useState<{ index: number } | null>(null);
	const [start, setStart] = useState(
		chapterNumbers.length ? String(Math.min(...chapterNumbers)) : "",
	);
	const [end, setEnd] = useState(
		chapterNumbers.length ? String(Math.max(...chapterNumbers)) : "",
	);
	const [batchSize, setBatchSize] = useState("100");
	// The job's input streams: chapters are always loaded, memories when a group is chosen.
	const inputs: TranslationJobCreateRequestInputs = memoryGroup
		? {
				memories: {
					type: "memories",
					memoryGroupId: memoryGroup,
					excludeCurrentChapter,
					pluginNames,
					memoryTypes,
				},
			}
		: {};
	// The backend type-checks the draft; this component only renders its answer.
	const [check, setCheck] = useState<TranslationPipelineCheck | null>(null);
	const stageActions = stages.map((stage) => stage.action.id).join(",");
	useEffect(() => {
		const controller = new AbortController();
		void checkTranslationJobsCheckPost(
			{
				novelId,
				// Types do not depend on the chapter range, which may be mid-edit.
				config: { batchSize: 1 },
				inputs: memoryGroup
					? { memories: { type: "memories", memoryGroupId: memoryGroup } }
					: {},
				stages: stageActions ? stageActions.split(",").map((action) => ({ action })) : [],
			},
			{ signal: controller.signal },
		)
			.then((response) => {
				if (!controller.signal.aborted)
					setCheck(response.status === 200 ? response.data : null);
			})
			.catch(() => {
				if (!controller.signal.aborted) setCheck(null);
			});
		return () => controller.abort();
	}, [novelId, memoryGroup, stageActions]);
	const addable = new Map(check?.addable.map((item) => [item.action, item.warning]));
	const validRange =
		[start, end, batchSize].every(
			(value) => value.trim() !== "" && Number.isSafeInteger(Number(value)),
		) &&
		Number(start) >= 0 &&
		Number(end) >= Number(start) &&
		Number(batchSize) > 0 &&
		Number.isSafeInteger(Number(end) + 1) &&
		chapterNumbers.some((number) => number >= Number(start) && number <= Number(end));
	function addStage() {
		const action = actions.find((item) => item.id === selected);
		if (!action || stages.length === 5) return;
		const config = Object.fromEntries(
			Object.entries(formSchema(action).properties ?? {}).flatMap(([name, field]) =>
				typeof field === "object" && field.default !== undefined
					? [[name, field.default]]
					: [],
			),
		);
		const stage = { id: crypto.randomUUID(), action, config };
		setStages([...stages, stage]);
		setSelected("");
		setConfiguring(stage.id);
	}
	async function submit() {
		if (submittingRef.current) return;
		const invalid = stages.findIndex(
			(stage) =>
				validator.validateFormData(stage.config, formSchema(stage.action)).errors.length >
				0,
		);
		if (invalid >= 0) {
			setConfiguring(stages[invalid].id);
			setError("Complete the configuration for stage " + (invalid + 1) + ".");
			return;
		}
		submittingRef.current = true;
		setSubmitting(true);
		setError(null);
		setStageErrors({});
		try {
			const response = await createTranslationJobsPost({
				novelId,
				config: {
					startChapterNum: Number(start),
					endChapterNum: Number(end) + 1,
					batchSize: Number(batchSize),
				},
				inputs,
				stages: stages.map((stage) => ({ action: stage.action.id, config: stage.config })),
			});
			if (response.status !== 201) {
				setError(apiErrorMessage(response.data, "Could not create translation job."));
				const data: unknown = response.data;
				if (
					typeof data === "object" &&
					data !== null &&
					"detail" in data &&
					Array.isArray(data.detail)
				) {
					const messages: Record<number, string> = {};
					for (const item of data.detail) {
						if (
							typeof item === "object" &&
							item !== null &&
							"loc" in item &&
							Array.isArray(item.loc) &&
							"msg" in item &&
							typeof item.msg === "string"
						) {
							const index = item.loc[item.loc.indexOf("stages") + 1];
							if (typeof index === "number")
								messages[index] = [messages[index], item.msg]
									.filter(Boolean)
									.join("; ");
						}
					}
					setStageErrors(messages);
				}
				return;
			}
			onCreate(response.data.jobId);
		} catch (error: unknown) {
			setError(requestErrorMessage(error));
		} finally {
			submittingRef.current = false;
			setSubmitting(false);
		}
	}
	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open && !submitting) onClose();
			}}
		>
			<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-6xl">
				<DialogHeader>
					<DialogTitle>Create translation job</DialogTitle>
					<DialogDescription>
						Choose source chapters and build a pipeline of up to five stages.
					</DialogDescription>
				</DialogHeader>
				{error && (
					<p role="alert" className="text-sm text-destructive">
						{error}
					</p>
				)}
				<fieldset disabled={submitting} className="min-w-0 space-y-5">
					<section className="space-y-4 rounded-lg bg-muted/50 p-4">
						<h3 className="font-medium">Inputs</h3>
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
								Enter a valid chapter range containing source chapters and a
								positive batch size.
							</p>
						)}
						<div className="flex items-end gap-2">
							<label className="flex-1 space-y-2 text-sm">
								Memory group
								<select
									className={selectClass}
									disabled={groups.status !== "ready"}
									value={memoryGroup}
									onChange={(event) => {
										setMemoryGroup(event.target.value);
										setSelected("");
									}}
								>
									<option value="">None</option>
									{groups.status === "ready" &&
										groups.data.map((group) => (
											<option
												key={group.memoryGroupId}
												value={group.memoryGroupId}
											>
												{group.memoryGroupName}
											</option>
										))}
								</select>
							</label>
							<Button
								variant="outline"
								disabled={!memoryGroup}
								aria-expanded={advanced && memoryGroup !== ""}
								onClick={() => setAdvanced(!advanced)}
							>
								Advanced
							</Button>
						</div>
						{advanced && memoryGroup && (
							<div className="space-y-3 rounded-lg border p-3">
								<label className="flex items-center gap-2 text-sm">
									<input
										type="checkbox"
										checked={excludeCurrentChapter}
										onChange={(event) =>
											setExcludeCurrentChapter(event.target.checked)
										}
									/>
									Exclude memories recorded from the chapter being translated
								</label>
								<div className="grid grid-cols-2 gap-3">
									<MemoryFilter
										title="Plugin names"
										allLabel="All plugin names"
										choices={Object.values(PluginName)}
										value={pluginNames}
										onChange={setPluginNames}
									/>
									<MemoryFilter
										title="Memory types"
										allLabel="All memory types"
										choices={Object.values(MemoryType)}
										value={memoryTypes}
										onChange={setMemoryTypes}
									/>
								</div>
							</div>
						)}
						{groups.status === "error" && (
							<div role="alert">
								{groups.message}{" "}
								<Button variant="outline" onClick={reloadGroups}>
									Retry memory groups
								</Button>
							</div>
						)}
						{(groups.status === "idle" || groups.status === "loading") && (
							<p role="status">Loading memory groups…</p>
						)}
						<p className="text-xs text-muted-foreground">
							Loaded for every stage:{" "}
							{check?.stages[0].outputs.map((port) => port.stream).join(" + ") ?? "…"}
						</p>
					</section>
					<div className="grid items-start gap-5 lg:grid-cols-2">
						<div className="min-w-0 space-y-3">
							<h3 className="font-medium">
								Stages{" "}
								<span className="text-muted-foreground">{stages.length} / 5</span>
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
												setConfiguring(
													configuring === stage.id ? null : stage.id,
												)
											}
										>
											{configuring === stage.id
												? "Cancel changes"
												: "Configure"}
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
									{check?.stages[index + 1] && (
										<p className="text-xs text-muted-foreground">
											Uses{" "}
											{check.stages[index + 1].inputs
												.filter((port) => port.link === "linked")
												.map((port) => port.stream)
												.join(" + ") || "nothing"}{" "}
											→ writes{" "}
											{check.stages[index + 1].outputs
												.map((port) => port.stream)
												.join(" + ")}
										</p>
									)}
									{check?.stages[index + 1]?.warning && (
										<p role="status" className="text-sm text-amber-600">
											This stage cannot run: {check.stages[index + 1].warning}
											.
										</p>
									)}
									<p className="text-sm">
										{[
											stage.config.model,
											stage.config.targetLanguage,
											stage.config.instructions
												? "Custom instructions"
												: null,
										]
											.filter((value) => typeof value === "string")
											.join(" · ") || "No configuration required"}
									</p>
									{stageErrors[index] && (
										<p role="alert" className="text-sm text-destructive">
											{stageErrors[index]}
										</p>
									)}
									{configuring === stage.id && (
										<StageConfigForm
											key={stage.id}
											schema={formSchema(stage.action)}
											config={stage.config}
											onSave={(config) => {
												setStages(
													stages.map((item) =>
														item.id === stage.id
															? { ...item, config }
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
										Remove stages {pending.index + 1}–{stages.length}?
									</p>
									<Button
										size="sm"
										variant="destructive"
										onClick={() => {
											setStages(stages.slice(0, pending.index));
											setConfiguring(null);
											setSelected("");
											setPending(null);
										}}
									>
										Remove stages
									</Button>{" "}
									<Button
										size="sm"
										variant="outline"
										onClick={() => setPending(null)}
									>
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
											<option value="">Select action</option>
											{actions.map((action) => {
												const warning = addable.get(action.id);
												return (
													<option
														key={action.id}
														value={action.id}
														disabled={warning !== null}
													>
														{action.label}
														{warning ? ` (${warning})` : ""}
													</option>
												);
											})}
										</select>
									</label>
									<Button
										disabled={
											!selected || pending !== null || configuring !== null
										}
										onClick={addStage}
									>
										Add stage
									</Button>
								</div>
							)}
						</div>
						{check && <PipelineDiagram check={check} />}
					</div>
					<div className="flex justify-end gap-2">
						<Button variant="outline" onClick={onClose}>
							Cancel
						</Button>
						<Button
							disabled={
								!validRange ||
								submitting ||
								stages.length === 0 ||
								configuring !== null ||
								pending !== null
							}
							onClick={submit}
						>
							{submitting ? "Creating…" : "Create job"}
						</Button>
					</div>
				</fieldset>
			</DialogContent>
		</Dialog>
	);
}
