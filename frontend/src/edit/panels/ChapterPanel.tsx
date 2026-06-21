import { useEffect, useState } from "react";
import { Effect } from "effect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus } from "lucide-react";
import type { EditorManager } from "../managers/editorManager";

export function ChapterPanel({ editorManager }: { editorManager: EditorManager }) {
	const [chapterIds, setChapterIds] = useState(editorManager.getters.chapterIds());
	const [currentId, setCurrentId] = useState(editorManager.getters.currentChapterId());
	const [showAdd, setShowAdd] = useState(false);
	const [newNum, setNewNum] = useState("");
	const [newTitle, setNewTitle] = useState("");

	useEffect(() => {
		const unsub = editorManager.subscribe(() => {
			setChapterIds(editorManager.getters.chapterIds());
			setCurrentId(editorManager.getters.currentChapterId());
			return Effect.succeed(void 0);
		});
		return unsub;
	}, [editorManager]);

	const handleAdd = () => {
		const num = parseInt(newNum, 10);
		if (isNaN(num) || !newTitle.trim()) return;
		console.time("addChapter full cycle");
		editorManager.addChapter(num, newTitle.trim(), false);
		console.timeEnd("addChapter full cycle");
		setNewNum("");
		setNewTitle("");
		setShowAdd(false);
	};

	return (
		<div className="flex flex-col gap-1 p-2">
			<div className="flex items-center gap-2 px-1.5 py-1">
				<span className="text-xs font-medium text-muted-foreground flex-1">
					Chapters
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
				<div className="flex flex-col gap-1 px-1.5 pb-1">
					<div className="flex gap-1">
						<Input
							className="h-7 text-xs w-16"
							placeholder="#"
							value={newNum}
							onChange={(e) => setNewNum(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleAdd();
								if (e.key === "Escape") setShowAdd(false);
							}}
						/>
						<Input
							className="h-7 text-xs flex-1"
							placeholder="Title"
							value={newTitle}
							onChange={(e) => setNewTitle(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter") handleAdd();
								if (e.key === "Escape") setShowAdd(false);
							}}
						/>
					</div>
					<Button size="sm" className="h-6 text-xs" onClick={handleAdd}>
						Add
					</Button>
				</div>
			)}
			{chapterIds.map((id) => (
				<div
					key={id}
					className={`px-1.5 py-1 rounded cursor-pointer text-xs ${
						id === currentId
							? "bg-accent font-medium"
							: "hover:bg-accent/50 text-muted-foreground"
					}`}
					onClick={() => editorManager.switchChapter(id)}
				>
					{id}
				</div>
			))}
			{chapterIds.length === 0 && (
				<div className="px-1.5 py-1 text-xs text-muted-foreground">
					No chapters yet.
				</div>
			)}
		</div>
	);
}
