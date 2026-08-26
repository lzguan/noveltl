import { editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch } from "@/api/endpoints/default/default";
import { ReviewStatus, type GlossaryTerm, type Memory } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuRadioGroup,
	DropdownMenuRadioItem,
	DropdownMenuSeparator,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { CalendarX2Icon, EllipsisIcon, LinkIcon, PencilIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { DeleteMemoryDialog } from "./DeleteMemoryDialog";
import { EditMemoryContentDialog } from "./EditMemoryContentDialog";
import { EditMemoryTermsDialog } from "./EditMemoryTermsDialog";
import { ExpireMemoryDialog } from "./ExpireMemoryDialog";

const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
	pending: "pending",
	approved: "approved",
	rejected: "rejected",
};

const MEMORY_TYPE_LABELS: Record<Memory["memoryType"], string> = {
	fact: "fact",
	event: "event",
	def: "definition",
	rel: "relation",
};

function reviewBadgeVariant(status: ReviewStatus) {
	if (status === "approved") return "default" as const;
	if (status === "rejected") return "destructive" as const;
	return "outline" as const;
}

function chapterRangeLabel(memory: Memory) {
	if (memory.memoryEndNum === null) return `Ch. ${memory.memoryStartNum}+`;
	const lastInclusive = memory.memoryEndNum - 1;
	return lastInclusive === memory.memoryStartNum
		? `Ch. ${memory.memoryStartNum}`
		: `Ch. ${memory.memoryStartNum}–${lastInclusive}`;
}

export function MemoryRow({
	memoryGroupId,
	memory,
	terms,
	chapterId,
	chapterNum,
	reloadMemories,
	reloadMemoriesAfterDelete,
	reloadTerms,
}: {
	memoryGroupId: string;
	memory: Memory;
	terms?: readonly GlossaryTerm[];
	chapterId: string | null;
	chapterNum: number | null;
	reloadMemories: () => void;
	reloadMemoriesAfterDelete: () => void;
	reloadTerms?: () => void;
}) {
	const associatedTerms = terms ?? [];
	const [editContentOpen, setEditContentOpen] = useState(false);
	const [editTermsOpen, setEditTermsOpen] = useState(false);
	const [expireOpen, setExpireOpen] = useState(false);
	const [deleteOpen, setDeleteOpen] = useState(false);
	const [reviewSubmitting, setReviewSubmitting] = useState(false);
	const [reviewError, setReviewError] = useState<string | null>(null);

	async function setReviewStatus(reviewStatus: ReviewStatus) {
		if (reviewStatus === memory.memoryReviewStatus) return;
		setReviewSubmitting(true);
		setReviewError(null);
		try {
			const response = await editMemoryReviewStatusMemoriesMemoryIdReviewStatusPatch(
				memory.memoryId,
				{ reviewStatus },
			);
			if (response.status !== 200) {
				setReviewError(
					apiErrorMessage(response.data, "Could not change the memory review status."),
				);
				return;
			}
			reloadMemories();
		} catch (error) {
			setReviewError(requestErrorMessage(error));
		} finally {
			setReviewSubmitting(false);
		}
	}

	return (
		<article className="border-b px-2 py-2 text-sm">
			<div className="flex flex-wrap items-center gap-1">
				<Badge variant={reviewBadgeVariant(memory.memoryReviewStatus)}>
					{REVIEW_STATUS_LABELS[memory.memoryReviewStatus]}
				</Badge>
				<Badge variant="secondary">{MEMORY_TYPE_LABELS[memory.memoryType]}</Badge>
				<span className="text-xs text-muted-foreground">
					{chapterRangeLabel(memory)} · {memory.creatorType}
				</span>
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button
							variant="ghost"
							size="icon-sm"
							className="ml-auto"
							aria-label="Memory actions"
							disabled={reviewSubmitting}
						>
							<EllipsisIcon />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end">
						<DropdownMenuItem onSelect={() => setEditContentOpen(true)}>
							<PencilIcon /> Edit content
						</DropdownMenuItem>
						{terms !== undefined && (
							<DropdownMenuItem onSelect={() => setEditTermsOpen(true)}>
								<LinkIcon /> Edit associated terms
							</DropdownMenuItem>
						)}
						<DropdownMenuSub>
							<DropdownMenuSubTrigger>Review status</DropdownMenuSubTrigger>
							<DropdownMenuSubContent>
								<DropdownMenuRadioGroup value={memory.memoryReviewStatus}>
									<DropdownMenuRadioItem
										value={ReviewStatus.pending}
										onSelect={() => void setReviewStatus(ReviewStatus.pending)}
									>
										Pending
									</DropdownMenuRadioItem>
									<DropdownMenuRadioItem
										value={ReviewStatus.approved}
										onSelect={() => void setReviewStatus(ReviewStatus.approved)}
									>
										Approved
									</DropdownMenuRadioItem>
									<DropdownMenuRadioItem
										value={ReviewStatus.rejected}
										onSelect={() => void setReviewStatus(ReviewStatus.rejected)}
									>
										Rejected
									</DropdownMenuRadioItem>
								</DropdownMenuRadioGroup>
							</DropdownMenuSubContent>
						</DropdownMenuSub>
						<DropdownMenuItem
							disabled={
								chapterId === null ||
								chapterNum === null ||
								chapterNum <= memory.memoryStartNum ||
								(memory.memoryEndNum !== null && chapterNum >= memory.memoryEndNum)
							}
							onSelect={() => setExpireOpen(true)}
						>
							<CalendarX2Icon /> Expire at current chapter
						</DropdownMenuItem>
						<DropdownMenuSeparator />
						<DropdownMenuItem
							variant="destructive"
							onSelect={() => setDeleteOpen(true)}
						>
							<Trash2Icon /> Delete
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
			{reviewError !== null && (
				<p role="alert" className="mt-1 text-xs text-destructive">
					{reviewError}
				</p>
			)}
			<div
				className={
					associatedTerms.length === 0
						? "mt-1"
						: "mt-2 grid gap-2 sm:grid-cols-[1fr_auto]"
				}
			>
				<p className="whitespace-pre-wrap">{memory.memoryContent}</p>
				{associatedTerms.length > 0 && (
					<div
						className="flex max-w-32 flex-wrap content-start gap-1"
						aria-label="Associated terms"
					>
						{associatedTerms.map((term) => (
							<Badge key={term.termId} variant="outline">
								{term.term}
							</Badge>
						))}
					</div>
				)}
			</div>
			{editContentOpen && (
				<EditMemoryContentDialog
					memory={memory}
					closeDialog={() => setEditContentOpen(false)}
					reloadMemories={reloadMemories}
				/>
			)}
			{editTermsOpen && terms !== undefined && (
				<EditMemoryTermsDialog
					memoryGroupId={memoryGroupId}
					memory={memory}
					terms={terms}
					closeDialog={() => setEditTermsOpen(false)}
					reloadMemories={reloadMemories}
					reloadTerms={reloadTerms}
				/>
			)}
			{expireOpen && chapterId !== null && (
				<ExpireMemoryDialog
					memory={memory}
					chapterId={chapterId}
					closeDialog={() => setExpireOpen(false)}
					reloadMemories={reloadMemories}
					reloadTerms={reloadTerms}
				/>
			)}
			{deleteOpen && (
				<DeleteMemoryDialog
					memory={memory}
					closeDialog={() => setDeleteOpen(false)}
					reloadMemoriesAfterDelete={reloadMemoriesAfterDelete}
					reloadTerms={reloadTerms}
				/>
			)}
		</article>
	);
}
