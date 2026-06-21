import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Eye, EyeOff, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Effect } from "effect";
import type { EditorManager, LabelGroupEntry } from "../managers/editorManager";

function LabelGroupRow({
	entry,
	chapterOpen,
	editorManager,
}: {
	entry: LabelGroupEntry;
	chapterOpen: boolean;
	editorManager: EditorManager;
}) {
	const isActive = entry.active;
	const isVisible = entry.visible;
	const isLoading = entry.status === "loading";
	const canReload = chapterOpen && (entry.status === "ready" || entry.status === "error");

	return (
		<div
			className={cn(
				"flex items-center gap-2 p-1.5 rounded cursor-pointer text-sm",
				isActive && "bg-accent",
			)}
			onClick={() => editorManager.setActive(entry.id)}
		>
			<div
				className="w-3 h-3 rounded-full shrink-0"
				style={{ backgroundColor: `#${entry.color.toString(16).padStart(6, "0")}` }}
			/>
			<span className="flex-1 truncate">{entry.name}</span>
			{isLoading ? (
				<Skeleton className="h-4 w-4 rounded" />
			) : (
				<Button
					variant="ghost"
					size="icon-sm"
					className="h-6 w-6 shrink-0"
					onClick={(e) => {
						e.stopPropagation();
						editorManager.toggleVisibility(entry.id);
					}}
				>
					{isVisible ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
				</Button>
			)}
			{canReload && (
				<Button
					variant="ghost"
					size="icon-sm"
					className="h-6 w-6 shrink-0"
					onClick={(e) => {
						e.stopPropagation();
						editorManager.reloadLabelData(entry.id);
					}}
				>
					<RefreshCw className="h-3.5 w-3.5" />
				</Button>
			)}
		</div>
	);
}

export function LabelGroupPanel({ editorManager }: { editorManager: EditorManager }) {
	const [entries, setEntries] = useState<LabelGroupEntry[]>(
		editorManager.getters.labelGroups(),
	);
	const [showAdd, setShowAdd] = useState(false);
	const [newName, setNewName] = useState("");

	useEffect(() => {
		const unsub = editorManager.subscribe(() => {
			setEntries(editorManager.getters.labelGroups());
			return Effect.succeed(void 0);
		});
		return unsub;
	}, [editorManager]);

	const handleAdd = () => {
		if (!newName.trim()) return;
		editorManager.addLabelGroup(newName.trim());
		setNewName("");
		setShowAdd(false);
	};

	const chapterOpen = editorManager.getters.currentChapterId() !== null;

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
			{entries.length === 0 ? (
				<div className="px-1.5 py-1 text-xs text-muted-foreground">
					No label groups yet.
				</div>
			) : (
				entries.map((e) => (
					<LabelGroupRow
						key={e.id}
						entry={e}
						chapterOpen={chapterOpen}
						editorManager={editorManager}
					/>
				))
			)}
		</div>
	);
}
