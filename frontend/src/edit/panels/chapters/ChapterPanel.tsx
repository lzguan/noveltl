import { useState } from "react";
import { actionUpdateChaptersVisibilityNovelsNovelIdChaptersVisibilityPost } from "@/api/endpoints/default/default";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { Globe, Lock, Plus } from "lucide-react";
import type { CProvId, ProvChapter } from "../../controller/types/idTypes";
import { BulkChapterVisibilityDialog } from "./BulkChapterVisibilityDialog";

export function ChapterPanel({
	novelId,
	chapters,
	currentChapterId,
	onSwitchChapter,
	onAddChapter,
	onChaptersVisibilityUpdated,
}: {
	novelId: string;
	chapters: ProvChapter[];
	currentChapterId: CProvId | null;
	onSwitchChapter: (id: CProvId) => void;
	onAddChapter: (num: number, title: string, isPublic: boolean) => void;
	onChaptersVisibilityUpdated: (chapterNums: readonly number[], isPublic: boolean) => void;
}) {
	const [showAdd, setShowAdd] = useState(false);
	const [editingVisibility, setEditingVisibility] = useState(false);
	const [showBulkVisibility, setShowBulkVisibility] = useState(false);
	const [pendingChapterNums, setPendingChapterNums] = useState<ReadonlySet<number>>(
		() => new Set(),
	);
	const [toggleError, setToggleError] = useState<string | null>(null);
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

	const handleToggleChapter = async (chapter: ProvChapter) => {
		if (pendingChapterNums.has(chapter.chapterNum)) return;
		setPendingChapterNums((prev) => new Set(prev).add(chapter.chapterNum));
		setToggleError(null);
		try {
			const resp = await actionUpdateChaptersVisibilityNovelsNovelIdChaptersVisibilityPost(
				novelId,
				{
					start: chapter.chapterNum,
					end: chapter.chapterNum,
					isPublic: !chapter.chapterIsPublic,
				},
			);
			if (resp.status !== 200) {
				setToggleError(apiErrorMessage(resp.data, "Could not update chapter visibility."));
				return;
			}
			onChaptersVisibilityUpdated(resp.data.updatedChapterNums, resp.data.isPublic);
		} catch (err: unknown) {
			setToggleError(requestErrorMessage(err));
		} finally {
			setPendingChapterNums((prev) => {
				const next = new Set(prev);
				next.delete(chapter.chapterNum);
				return next;
			});
		}
	};

	return (
		<div className="flex flex-col gap-1 p-2">
			<div className="flex items-center gap-1 px-1.5 py-1">
				<span className="text-xs font-medium text-muted-foreground flex-1">Chapters</span>
				<Button
					variant={editingVisibility ? "secondary" : "ghost"}
					size="icon-sm"
					className="h-5 w-5"
					aria-label="Manage chapter visibility"
					aria-pressed={editingVisibility}
					title="Manage chapter visibility"
					disabled={chapters.length === 0}
					onClick={() => {
						setEditingVisibility((prev) => !prev);
						setToggleError(null);
					}}
				>
					<Globe className="h-3 w-3" />
				</Button>
				<Button
					variant="ghost"
					size="icon-sm"
					className="h-5 w-5"
					aria-label="Add chapter"
					title="Add chapter"
					onClick={() => setShowAdd(!showAdd)}
				>
					<Plus className="h-3 w-3" />
				</Button>
			</div>
			{editingVisibility && (
				<div className="flex flex-col gap-1 px-1.5 pb-1">
					<div className="flex items-center gap-1">
						<Button
							type="button"
							variant="outline"
							size="sm"
							className="h-6 flex-1 text-xs"
							onClick={() => setShowBulkVisibility(true)}
						>
							Bulk edit…
						</Button>
						<Button
							type="button"
							variant="ghost"
							size="sm"
							className="h-6 text-xs"
							onClick={() => {
								setEditingVisibility(false);
								setToggleError(null);
							}}
						>
							Done
						</Button>
					</div>
					{toggleError !== null && (
						<p role="alert" className="text-xs text-destructive">
							{toggleError}
						</p>
					)}
				</div>
			)}
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
			{chapters.map((c) => {
				const isPending = pendingChapterNums.has(c.chapterNum);
				return (
					<div
						key={c.chapterId}
						className={`flex items-center gap-1 px-1.5 py-1 rounded text-xs ${
							c.chapterId === currentChapterId
								? "bg-accent font-medium"
								: "hover:bg-accent/50 text-muted-foreground"
						}`}
					>
						<button
							type="button"
							className="min-w-0 flex-1 truncate text-left cursor-pointer"
							onClick={() => onSwitchChapter(c.chapterId)}
						>
							Ch.{c.chapterNum}: {c.chapterTitle}
						</button>
						{editingVisibility ? (
							<Button
								type="button"
								variant="ghost"
								size="icon-sm"
								className="h-5 w-5 shrink-0"
								disabled={isPending}
								aria-label={
									c.chapterIsPublic
										? `Make chapter ${c.chapterNum} private`
										: `Make chapter ${c.chapterNum} public`
								}
								title={c.chapterIsPublic ? "Make private" : "Make public"}
								onClick={() => void handleToggleChapter(c)}
							>
								{c.chapterIsPublic ? (
									<Globe className="h-3 w-3 text-foreground" />
								) : (
									<Lock className="h-3 w-3 text-muted-foreground" />
								)}
							</Button>
						) : c.chapterIsPublic ? (
							<Globe
								className="h-3 w-3 shrink-0 text-muted-foreground/70"
								aria-label="Public"
							/>
						) : (
							<Lock
								className="h-3 w-3 shrink-0 text-muted-foreground/40"
								aria-label="Private"
							/>
						)}
					</div>
				);
			})}
			{chapters.length === 0 && (
				<div className="px-1.5 py-1 text-xs text-muted-foreground">No chapters yet.</div>
			)}
			{showBulkVisibility && (
				<BulkChapterVisibilityDialog
					novelId={novelId}
					chapters={chapters}
					onUpdated={onChaptersVisibilityUpdated}
					onClose={() => setShowBulkVisibility(false)}
				/>
			)}
		</div>
	);
}
