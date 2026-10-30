import { readUI } from "./schemaUi";
import type { FieldProps } from "@rjsf/utils";

/** null means unrestricted; an explicit empty list intentionally matches nothing. */
export function ConfigFilterField({
	schema,
	formData,
	onChange,
	fieldPathId,
	registry,
	disabled,
	readonly,
}: FieldProps) {
	const items = schema.items;
	const itemSchema =
		items && typeof items === "object" && !Array.isArray(items)
			? registry.schemaUtils.retrieveSchema(items)
			: {};
	const choices = itemSchema.enum ?? [];
	const selected = Array.isArray(formData) ? formData : null;
	const title = schema.title ?? "Filter";
	return (
		<fieldset disabled={disabled || readonly} className="space-y-2 rounded-md border p-3">
			<legend className="px-1 text-sm font-medium">{title}</legend>
			<label className="flex items-center gap-2 text-sm">
				<input
					type="checkbox"
					checked={selected === null}
					onChange={(event) =>
						onChange(event.target.checked ? null : [], fieldPathId.path)
					}
				/>
				{readUI(schema).nullLabel ?? "All"}
			</label>
			{selected !== null && (
				<>
					<p className="text-xs text-muted-foreground">
						{readUI(schema).emptyLabel ?? "Select values to include."}
					</p>
					{choices.map((choice) => (
						<label key={String(choice)} className="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								checked={selected.includes(choice)}
								onChange={(event) =>
									onChange(
										event.target.checked
											? [...selected, choice]
											: selected.filter((value) => value !== choice),
										fieldPathId.path,
									)
								}
							/>
							{String(choice)}
						</label>
					))}
				</>
			)}
		</fieldset>
	);
}
