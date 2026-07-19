import { useRef, useState, type ComponentType } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { SepPriority } from "@/api/models";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

export interface AutoLabelCustomParamFieldProps {
	value: unknown;
	disabled?: boolean;
	onChange: (value: unknown) => void;
	onValidityChange: (valid: boolean) => void;
}

interface SeparatorRow {
	id: number;
	key: string;
	priority: SepPriority;
}

function separatorLength(value: string) {
	return Array.from(value).length;
}

function displaySeparator(value: string) {
	return value === "\n" ? "\\n" : value;
}

function readSeparator(value: string) {
	return value === "\\n" ? "\n" : value;
}

function readPriority(value: string): SepPriority {
	if (value === "1") return 1;
	if (value === "2") return 2;
	return 3;
}

function readSeparatorRows(value: unknown, nextId: React.RefObject<number>): SeparatorRow[] {
	if (typeof value !== "object" || value === null) return [];

	const rows: SeparatorRow[] = [];
	for (const [key, priority] of Object.entries(value)) {
		if (priority !== 1 && priority !== 2 && priority !== 3) continue;
		rows.push({
			id: nextId.current++,
			key,
			priority,
		});
	}
	return rows;
}

function validateRows(rows: SeparatorRow[]) {
	const counts = new Map<string, number>();
	for (const row of rows) {
		counts.set(row.key, (counts.get(row.key) ?? 0) + 1);
	}

	return rows.map((row) => {
		if (separatorLength(row.key) !== 1) return "Enter exactly one character.";
		if ((counts.get(row.key) ?? 0) > 1) return "Separator characters must be unique.";
		return null;
	});
}

function SeparatorRecordField({
	value,
	onChange,
	onValidityChange,
	disabled,
}: AutoLabelCustomParamFieldProps) {
	const nextId = useRef(0);
	const [rows, setRows] = useState<SeparatorRow[]>(() => readSeparatorRows(value, nextId));
	const errors = validateRows(rows);

	const updateRows = (nextRows: SeparatorRow[]) => {
		setRows(nextRows);
		const valid = validateRows(nextRows).every((error) => error === null);
		onValidityChange(valid);
		if (!valid) return;

		const separators: Record<string, SepPriority> = {};
		for (const row of nextRows) {
			separators[row.key] = row.priority;
		}
		onChange(separators);
	};

	return (
		<FieldSet>
			<FieldLabel>Separators</FieldLabel>
			<FieldGroup className="gap-2">
				{rows.map((row, index) => (
					<Field key={row.id} data-invalid={errors[index] !== null}>
						<div className="flex items-center gap-1">
							<Input
								className="h-8 min-w-0 flex-1 text-xs"
								value={displaySeparator(row.key)}
								disabled={disabled}
								aria-label={`Separator ${index + 1}`}
								aria-invalid={errors[index] !== null}
								onChange={(event) => {
									const key = readSeparator(event.target.value);
									updateRows(
										rows.map((candidate) =>
											candidate.id === row.id
												? { ...candidate, key }
												: candidate,
										),
									);
								}}
							/>
							<Select
								value={String(row.priority)}
								disabled={disabled}
								onValueChange={(priority) => {
									updateRows(
										rows.map((candidate) =>
											candidate.id === row.id
												? { ...candidate, priority: readPriority(priority) }
												: candidate,
										),
									);
								}}
							>
								<SelectTrigger
									size="sm"
									className="h-8 w-24 text-xs"
									aria-label={`Priority for separator ${displaySeparator(row.key)}`}
								>
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectGroup>
										<SelectItem value="1">HIGH</SelectItem>
										<SelectItem value="2">MED</SelectItem>
										<SelectItem value="3">LOW</SelectItem>
									</SelectGroup>
								</SelectContent>
							</Select>
							<Button
								type="button"
								size="icon-xs"
								variant="ghost"
								disabled={disabled}
								aria-label={`Remove separator ${displaySeparator(row.key)}`}
								onClick={() =>
									updateRows(rows.filter((candidate) => candidate.id !== row.id))
								}
							>
								<Trash2 />
							</Button>
						</div>
						{errors[index] && <FieldError>{errors[index]}</FieldError>}
					</Field>
				))}
				<Button
					type="button"
					size="xs"
					variant="outline"
					className="self-start"
					disabled={disabled}
					onClick={() =>
						updateRows([
							...rows,
							{
								id: nextId.current++,
								key: "",
								priority: 3,
							},
						])
					}
				>
					<Plus data-icon="inline-start" />
					Add separator
				</Button>
			</FieldGroup>
		</FieldSet>
	);
}

export const autoLabelCustomParamFields: Record<
	string,
	ComponentType<AutoLabelCustomParamFieldProps>
> = {
	separators: SeparatorRecordField,
};
