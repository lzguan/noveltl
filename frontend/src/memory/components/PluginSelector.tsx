import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useId } from "react";

export type MemoryView = "memories" | "glossary";

function isMemoryView(value: string): value is MemoryView {
	return value === "memories" || value === "glossary";
}

export function PluginSelector({
	value,
	onChange,
	compact = false,
}: {
	value: MemoryView;
	onChange: (value: MemoryView) => void;
	compact?: boolean;
}) {
	const selectorId = useId();

	return (
		<div
			className={
				compact ? "flex w-40 shrink-0 flex-col gap-1" : "flex flex-col gap-1 border-b p-2"
			}
		>
			<Label htmlFor={selectorId} className="text-xs text-muted-foreground">
				Plugin
			</Label>
			<Select
				value={value}
				onValueChange={(nextValue) => {
					if (isMemoryView(nextValue)) onChange(nextValue);
				}}
			>
				<SelectTrigger id={selectorId} size="sm" className="w-full">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					<SelectItem value="memories">View all memories</SelectItem>
					<SelectItem value="glossary">Glossary</SelectItem>
				</SelectContent>
			</Select>
		</div>
	);
}
