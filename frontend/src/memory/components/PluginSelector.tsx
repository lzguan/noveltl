import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

export type MemoryView = "memories" | "glossary";

function isMemoryView(value: string): value is MemoryView {
	return value === "memories" || value === "glossary";
}

export function PluginSelector({
	value,
	onChange,
}: {
	value: MemoryView;
	onChange: (value: MemoryView) => void;
}) {
	return (
		<div className="flex flex-col gap-1 border-b p-2">
			<Label htmlFor="memory-plugin-selector" className="text-xs text-muted-foreground">
				Plugin
			</Label>
			<Select
				value={value}
				onValueChange={(nextValue) => {
					if (isMemoryView(nextValue)) onChange(nextValue);
				}}
			>
				<SelectTrigger id="memory-plugin-selector" size="sm" className="w-full">
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
