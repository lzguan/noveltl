import type { MemoryGroup } from "@/api/models";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

export function MemoryGroupSelector({
	groups,
	selectedGroupId,
	onSelect,
}: {
	groups: readonly MemoryGroup[];
	selectedGroupId: string;
	onSelect: (memoryGroupId: string) => void;
}) {
	return (
		<div className="flex flex-col gap-1 border-b p-2">
			<Label htmlFor="memory-group-selector" className="text-xs text-muted-foreground">
				Memory group
			</Label>
			<Select value={selectedGroupId} onValueChange={onSelect}>
				<SelectTrigger id="memory-group-selector" size="sm" className="w-full">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					{groups.map((group) => (
						<SelectItem key={group.memoryGroupId} value={group.memoryGroupId}>
							{group.memoryGroupName}
							<span className="text-muted-foreground">· {group.memoryLanguage}</span>
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		</div>
	);
}
