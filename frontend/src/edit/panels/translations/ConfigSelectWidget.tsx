import type { WidgetProps } from "@rjsf/utils";

/** Preserve the schema field's label association for dynamic enum controls. */
export function ConfigSelectWidget({
	id,
	options,
	value,
	multiple,
	required,
	disabled,
	readonly,
	onChange,
	onBlur,
	onFocus,
}: WidgetProps) {
	const choices = options.enumOptions ?? [];
	const selected = multiple
		? choices.flatMap((choice, index) =>
				Array.isArray(value) && value.includes(choice.value) ? [String(index)] : [],
			)
		: String(choices.findIndex((choice) => choice.value === value));
	return (
		<select
			id={id}
			className="min-h-9 w-full rounded-md border bg-background px-2 text-sm"
			multiple={multiple}
			required={required}
			disabled={disabled || readonly}
			value={selected}
			onChange={(event) =>
				onChange(
					multiple
						? Array.from(
								event.target.selectedOptions,
								(option) => choices[Number(option.value)].value,
							)
						: choices[Number(event.target.value)]?.value,
				)
			}
			onBlur={() => onBlur(id, value)}
			onFocus={() => onFocus(id, value)}
		>
			{!multiple && <option value="-1">Select an option</option>}
			{choices.map((choice, index) => (
				<option
					key={index}
					value={String(index)}
					disabled={options.enumDisabled?.includes(choice.value)}
				>
					{choice.label}
				</option>
			))}
		</select>
	);
}
