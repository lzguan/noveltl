import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Eye, EyeOff, Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import type { LGProvId } from "../../controller/types/idTypes";
import type { LabelGroupView } from "../../hooks/useTrackedLabelGroups";

function LabelGroupRow({
	id,
	view,
	chapterOpen,
	onSetActive,
	onToggleVisibility,
	onReloadLabelData,
}: {
	id: LGProvId;
	view: LabelGroupView;
	chapterOpen: boolean;
	onSetActive: (id: LGProvId | null) => void;
	onToggleVisibility: (id: LGProvId) => void;
	onReloadLabelData: (id: LGProvId) => void;
}) {
	const canReload = chapterOpen;

	const statusClass = (() => {
		switch (view.status) {
			case "ready":
				return "shadow-sm ring-1 ring-foreground/10";
			case "loading":
				return "animate-pulse";
			case "error":
				return "ring-1 ring-red-500";
			default:
				return "opacity-30";
		}
	})();

	return (
		<div
			className={cn(
				"flex items-center gap-2 p-1.5 rounded cursor-pointer text-sm",
				view.active && "bg-accent",
			)}
			onClick={() => onSetActive(id)}
		>
			<div
				className={cn("w-3 h-3 rounded-full shrink-0", statusClass)}
				style={{ backgroundColor: `#${view.color.toString(16).padStart(6, "0")}` }}
			/>
			<span className="flex-1 truncate">{view.labelGroup.labelGroupName}</span>
			<Button
				variant="ghost"
				size="icon-sm"
				className="h-6 w-6 shrink-0"
				onClick={(e) => {
					e.stopPropagation();
					onToggleVisibility(id);
				}}
			>
				{view.visible ? (
					<Eye className="h-3.5 w-3.5" />
				) : (
					<EyeOff className="h-3.5 w-3.5" />
				)}
			</Button>
			{canReload && (
				<Button
					variant="ghost"
					size="icon-sm"
					className="h-6 w-6 shrink-0"
					onClick={(e) => {
						e.stopPropagation();
						onReloadLabelData(id);
					}}
				>
					<RefreshCw className="h-3.5 w-3.5" />
				</Button>
			)}
		</div>
	);
}

export function LabelGroupPanel({
	labelGroups,
	chapterOpen,
	onToggleVisibility,
	onSetActive,
	onAddLabelGroup,
	onReloadLabelData,
}: {
	labelGroups: [LGProvId, LabelGroupView][];
	chapterOpen: boolean;
	onToggleVisibility: (id: LGProvId) => void;
	onSetActive: (id: LGProvId | null) => void;
	onAddLabelGroup: (name: string) => void;
	onReloadLabelData: (id: LGProvId) => void;
}) {
	const [showAdd, setShowAdd] = useState(false);
	const [newName, setNewName] = useState("");

	const handleAdd = () => {
		if (!newName.trim()) return;
		onAddLabelGroup(newName.trim());
		setNewName("");
		setShowAdd(false);
	};

	return (
		<div className="flex flex-col gap-0.5 p-2">
			<div className="flex items-center gap-2 px-1.5 py-1">
				<span className="text-xs font-medium text-muted-foreground flex-1">
					Label Groups
				</span>
				<Button
					variant="ghost"
					size="icon-sm"
					className="h-5 w-5"
					onClick={() => setShowAdd(!showAdd)}
				>
					<Plus className="h-3 w-3" />
				</Button>
			</div>
			{showAdd && (
				<div className="flex gap-1 px-1.5 pb-1">
					<Input
						className="h-7 text-xs flex-1"
						placeholder="Label group name"
						value={newName}
						onChange={(e) => setNewName(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter") handleAdd();
							if (e.key === "Escape") setShowAdd(false);
						}}
					/>
					<Button size="sm" className="h-7 text-xs" onClick={handleAdd}>
						Add
					</Button>
				</div>
			)}
			{labelGroups.length === 0 ? (
				<div className="px-1.5 py-1 text-xs text-muted-foreground">
					No label groups yet.
				</div>
			) : (
				labelGroups.map(([id, view]) => (
					<LabelGroupRow
						key={id}
						id={id}
						view={view}
						chapterOpen={chapterOpen}
						onSetActive={onSetActive}
						onToggleVisibility={onToggleVisibility}
						onReloadLabelData={onReloadLabelData}
					/>
				))
			)}
		</div>
	);
}
