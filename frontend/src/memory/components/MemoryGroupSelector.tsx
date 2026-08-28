import type { MemoryGroup } from "@/api/models";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { ChevronDownIcon, PlusIcon } from "lucide-react";
import { useId, useState } from "react";

export function MemoryGroupSelector({
	groups,
	selectedGroupId,
	onSelect,
	onCreate,
}: {
	groups: readonly MemoryGroup[];
	selectedGroupId: string;
	onSelect: (memoryGroupId: string) => void;
	onCreate: () => void;
}) {
	const [open, setOpen] = useState(false);
	const selectorId = useId();
	const selectedGroup = groups.find((group) => group.memoryGroupId === selectedGroupId);

	return (
		<Collapsible open={open} onOpenChange={setOpen} className="border-b">
			<CollapsibleTrigger asChild>
				<Button
					variant="ghost"
					className="h-auto w-full justify-between rounded-none px-2 py-2"
				>
					<span className="min-w-0 text-left">
						<span className="block text-xs font-normal text-muted-foreground">
							Memory group
						</span>
						<span className="block truncate text-sm">
							{selectedGroup?.memoryGroupName ?? "Select a memory group"}
							{selectedGroup !== undefined && (
								<span className="font-normal text-muted-foreground">
									{" "}
									· {selectedGroup.memoryLanguage}
								</span>
							)}
						</span>
					</span>
					<ChevronDownIcon
						className={
							open ? "rotate-180 transition-transform" : "transition-transform"
						}
					/>
				</Button>
			</CollapsibleTrigger>
			<CollapsibleContent className="px-2 pb-2">
				<Label htmlFor={selectorId} className="sr-only">
					Memory group
				</Label>
				<div className="flex items-center gap-1.5">
					<Select
						value={selectedGroupId}
						onValueChange={(memoryGroupId) => {
							onSelect(memoryGroupId);
							setOpen(false);
						}}
					>
						<SelectTrigger id={selectorId} size="sm" className="min-w-0 flex-1">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{groups.map((group) => (
								<SelectItem key={group.memoryGroupId} value={group.memoryGroupId}>
									{group.memoryGroupName}
									<span className="text-muted-foreground">
										· {group.memoryLanguage}
									</span>
								</SelectItem>
							))}
						</SelectContent>
					</Select>
					<Button
						variant="outline"
						size="icon-sm"
						aria-label="Create memory group"
						title="Create memory group"
						onClick={onCreate}
					>
						<PlusIcon />
					</Button>
				</div>
			</CollapsibleContent>
		</Collapsible>
	);
}
