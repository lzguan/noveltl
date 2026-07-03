import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus } from "lucide-react";
import type { CProvId, ProvChapter } from "../controller/types/idTypes";

export function ChapterPanel({
	chapters,
	currentChapterId,
	onSwitchChapter,
	onAddChapter,
}: {
	chapters: ProvChapter[];
	currentChapterId: CProvId | null;
	onSwitchChapter: (id: CProvId) => void;
	onAddChapter: (num: number, title: string, isPublic: boolean) => void;
}) {
	const [showAdd, setShowAdd] = useState(false);
	const [newNum, setNewNum] = useState("");
	const [newTitle, setNewTitle] = useState("");

	const handleAdd = () => {
		const num = parseInt(newNum, 10);
		if (isNaN(num) || !newTitle.trim()) return;
		onAddChapter(num, newTitle.trim(), false);
		setNewNum("");
		setNewTitle("");
		setShowAdd(false);
	};

	return (
		<div className="flex flex-col gap-1 p-2">
			<div className="flex items-center gap-2 px-1.5 py-1">
				<span className="text-xs font-medium text-muted-foreground flex-1">Chapters</span>
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
			{chapters.map((c) => (
				<div
					key={c.chapterId}
					className={`px-1.5 py-1 rounded cursor-pointer text-xs ${
						c.chapterId === currentChapterId
							? "bg-accent font-medium"
							: "hover:bg-accent/50 text-muted-foreground"
					}`}
					onClick={() => onSwitchChapter(c.chapterId)}
				>
					Ch.{c.chapterNum}: {c.chapterTitle}
				</div>
			))}
			{chapters.length === 0 && (
				<div className="px-1.5 py-1 text-xs text-muted-foreground">No chapters yet.</div>
			)}
		</div>
	);
}
