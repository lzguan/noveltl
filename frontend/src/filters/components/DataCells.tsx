import { readLabelLabelsLabelIdGet } from "@/api/endpoints/default/default";
import type { DataType, GroupData, LabelRef, MDataType, TextSpan } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Popover,
	PopoverContent,
	PopoverHeader,
	PopoverTitle,
	PopoverTrigger,
} from "@/components/ui/popover";
import { CCServId, CServId } from "@/edit/controller/types/idTypes";
import { Info } from "lucide-react";
import { useState } from "react";

function shortId(value: string) {
	return value.slice(0, 8);
}

function Metadata({ values }: { values: readonly [string, string | number][] }) {
	return (
		<dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
			{values.map(([label, value]) => (
				<div className="contents" key={label}>
					<dt className="text-muted-foreground">{label}</dt>
					<dd className="min-w-0 break-all">{value}</dd>
				</div>
			))}
		</dl>
	);
}

export function TextSpanCell({
	value,
	gotoText,
}: {
	value: TextSpan;
	gotoText?: (chapterId: CServId, reference: { start: number; end: number; ccServId: CCServId }) => void;
}) {
	return (
		<div className="flex items-center gap-1">
			<Button
				type="button"
				variant="ghost"
				size="xs"
				disabled={!gotoText}
				onDoubleClick={() => gotoText?.(CServId(value.chapterId), { start: value.start, end: value.end, ccServId: CCServId(value.chapterContentId) })}
				title="Double-click to open this text span"
			>
				{shortId(value.chapterId)}:{value.start}–{value.end}
			</Button>
			<Popover>
				<PopoverTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						size="icon-xs"
						aria-label="Text span info"
					>
						<Info />
					</Button>
				</PopoverTrigger>
				<PopoverContent align="start">
					<PopoverHeader>
						<PopoverTitle>Text span</PopoverTitle>
					</PopoverHeader>
					<Metadata
						values={[
							["Chapter", value.chapterId],
							["Content", value.chapterContentId],
							["Range", `${value.start}–${value.end}`],
						]}
					/>
				</PopoverContent>
			</Popover>
		</div>
	);
}

export function LabelCell({
	value,
	gotoText,
}: {
	value: LabelRef;
	gotoText?: (chapterId: CServId, reference: { start: number; end: number; ccServId: CCServId }) => void;
}) {
	const gotoLabel = async () => {
		if (!gotoText) return;
		const response = await readLabelLabelsLabelIdGet(value.labelId);
		if (response.status !== 200) {
			console.error("Failed to read label", response.status, response.data);
			return;
		}
		const label = response.data;
		gotoText(CServId(value.chapterId), {
			start: label.labelStart,
			end: label.labelEnd,
			ccServId: CCServId(value.chapterContentId),
		});
	}
	return (
		<div className="flex items-center gap-1">
			<Button
				type="button"
				variant="ghost"
				size="xs"
				disabled={!gotoText}
				onDoubleClick={() => gotoLabel()}
				title="Double-click to open this label"
			>
				Label {shortId(value.labelId)}
			</Button>
			<Popover>
				<PopoverTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						size="icon-xs"
						aria-label="Label reference info"
					>
						<Info />
					</Button>
				</PopoverTrigger>
				<PopoverContent align="start">
					<PopoverHeader>
						<PopoverTitle>Label reference</PopoverTitle>
					</PopoverHeader>
					<Metadata
						values={[
							["Label", value.labelId],
							["Label data", value.labelDataId],
							["Label group", value.labelGroupId],
							["Chapter", value.chapterId],
							["Content", value.chapterContentId],
						]}
					/>
				</PopoverContent>
			</Popover>
		</div>
	);
}

export function GroupDataCell({ value }: { value: GroupData | undefined }) {
	if (!value) return <span className="text-muted-foreground">—</span>;
	if (value.type === "bool")
		return <Badge variant="outline">{value.value ? "true" : "false"}</Badge>;
	return <span>{value.value}</span>;
}

export function isMutableDataType(value: DataType | undefined): value is MDataType {
	return (
		value?.type === "string" ||
		value?.type === "int" ||
		value?.type === "float" ||
		value?.type === "bool"
	);
}

function scalarValue(value: MDataType) {
	if (value.type === "bool") return value.value ? "true" : "false";
	return value.value;
}

function initialDraft(value: MDataType): string | boolean {
	return value.type === "bool" ? value.value : String(value.value);
}

function parseDraft(value: MDataType, draft: string | boolean): MDataType {
	if (value.type === "bool") {
		return { kind: "value", type: "bool", value: draft === true };
	}
	const text = typeof draft === "string" ? draft : "";
	if (value.type === "string") {
		return { kind: "value", type: "string", value: text };
	}
	if (text.trim() === "") throw new Error("Enter a number.");
	const parsed = Number(text);
	if (value.type === "int") {
		if (!Number.isInteger(parsed)) throw new Error("Enter a whole number.");
		return { kind: "value", type: "int", value: parsed };
	}
	if (!Number.isFinite(parsed)) throw new Error("Enter a finite number.");
	return { kind: "value", type: "float", value: parsed };
}

export function MutableDataCell({
	value,
	editLabel,
	editingLocked,
	setEditingLocked,
	commit,
}: {
	value: MDataType;
	editLabel: string;
	editingLocked: boolean;
	setEditingLocked: (locked: boolean) => void;
	commit: (value: MDataType) => Promise<void>;
}) {
	const [isEditing, setIsEditing] = useState(false);
	const [draft, setDraft] = useState<string | boolean>(() => initialDraft(value));
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	function beginEditing() {
		if (editingLocked) return;
		setDraft(initialDraft(value));
		setError(null);
		setEditingLocked(true);
		setIsEditing(true);
	}

	function cancelEditing() {
		if (submitting) return;
		setIsEditing(false);
		setDraft(initialDraft(value));
		setError(null);
		setEditingLocked(false);
	}

	async function submitValue(event: React.SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		if (submitting) return;
		let nextValue: MDataType;
		try {
			nextValue = parseDraft(value, draft);
		} catch (parseError) {
			setError(parseError instanceof Error ? parseError.message : "Enter a valid value.");
			return;
		}

		setSubmitting(true);
		setError(null);
		try {
			await commit(nextValue);
			setIsEditing(false);
			setEditingLocked(false);
		} catch (commitError) {
			setError(
				commitError instanceof Error
					? commitError.message
					: "The value could not be saved.",
			);
		} finally {
			setSubmitting(false);
		}
	}

	if (!isEditing) {
		return (
			<Button
				type="button"
				variant="ghost"
				size="xs"
				disabled={editingLocked}
				onClick={beginEditing}
				aria-label={`Edit ${editLabel}`}
			>
				{scalarValue(value)}
			</Button>
		);
	}

	return (
		<form
			onSubmit={submitValue}
			onKeyDown={(event) => {
				if (event.key === "Escape") {
					event.preventDefault();
					cancelEditing();
				} else if (event.key === "Enter") {
					event.preventDefault();
					event.currentTarget.requestSubmit();
				}
			}}
			onBlur={(event) => {
				if (
					event.relatedTarget instanceof Node &&
					event.currentTarget.contains(event.relatedTarget)
				)
					return;
				cancelEditing();
			}}
			className="flex min-w-36 flex-col gap-1"
		>
			{value.type === "bool" ? (
				<label className="flex items-center gap-2 text-sm">
					<input
						type="checkbox"
						checked={draft === true}
						disabled={submitting}
						onChange={(event) => setDraft(event.target.checked)}
						className="size-4 accent-primary"
						autoFocus
					/>
					{draft === true ? "true" : "false"}
				</label>
			) : (
				<Input
					type={value.type === "string" ? "text" : "number"}
					step={value.type === "int" ? "1" : value.type === "float" ? "any" : undefined}
					value={typeof draft === "string" ? draft : ""}
					disabled={submitting}
					onChange={(event) => setDraft(event.target.value)}
					aria-label={editLabel}
					autoFocus
				/>
			)}
			<p className="text-xs text-muted-foreground">Press Enter to save · Esc to cancel</p>
			{error && <FieldError>{error}</FieldError>}
		</form>
	);
}

export function DataCell({
	value,
	gotoText,
}: {
	value: DataType | undefined;
	gotoText?: (chapterId: CServId, reference: { start: number; end: number; ccServId: CCServId }) => void;
}) {
	if (!value) return <span className="text-muted-foreground">—</span>;

	switch (value.type) {
		case "string":
		case "int":
		case "float":
			return <span>{value.value}</span>;
		case "bool":
			return <Badge variant="outline">{value.value ? "true" : "false"}</Badge>;
		case "textSpan":
			return <TextSpanCell value={value.value} gotoText={gotoText} />;
		case "labelRef":
			return <LabelCell value={value.value} gotoText={gotoText} />;
	}
}
