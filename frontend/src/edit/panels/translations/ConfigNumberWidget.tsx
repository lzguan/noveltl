import type { WidgetProps } from "@rjsf/utils";
import { ariaDescribedByIds, getSchemaType } from "@rjsf/utils";
import { Input } from "@/components/ui/input";

export function ConfigNumberWidget({
	id,
	value,
	schema,
	required,
	disabled,
	readonly,
	onChange,
	onBlur,
	onFocus,
	placeholder,
}: WidgetProps) {
	return (
		<Input
			id={id}
			type="number"
			value={value ?? ""}
			step={getSchemaType(schema) === "integer" ? 1 : "any"}
			min={schema.minimum}
			max={schema.maximum}
			required={required}
			disabled={disabled}
			readOnly={readonly}
			placeholder={placeholder}
			aria-describedby={ariaDescribedByIds(id)}
			onChange={(event) =>
				onChange(event.target.value === "" ? undefined : event.target.value)
			}
			onBlur={() => onBlur(id, value)}
			onFocus={() => onFocus(id, value)}
		/>
	);
}
