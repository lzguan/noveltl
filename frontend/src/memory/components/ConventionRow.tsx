import { editConventionReviewStatusMemoryGroupsMemoryGroupIdConventionsConventionIdReviewStatusPatch } from "@/api/endpoints/default/default";
import { ReviewStatus, type ConventionRead } from "@/api/models";
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
import { EllipsisIcon, PencilIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { ConventionDialog } from "./ConventionDialog";
import { DeleteConventionDialog } from "./DeleteConventionDialog";

const CATEGORY_LABELS: Record<ConventionRead["category"], string> = {
	naming: "naming",
	style: "style",
};

function reviewBadgeVariant(status: ReviewStatus) {
	if (status === "approved") return "default" as const;
	if (status === "rejected") return "destructive" as const;
	return "outline" as const;
}

export function ConventionRow({
	memoryGroupId,
	convention,
	reloadConventions,
	reloadConventionsAfterDelete,
}: {
	memoryGroupId: string;
	convention: ConventionRead;
	reloadConventions: () => void;
	reloadConventionsAfterDelete: () => void;
}) {
	const [editOpen, setEditOpen] = useState(false);
	const [deleteOpen, setDeleteOpen] = useState(false);
	const [reviewSubmitting, setReviewSubmitting] = useState(false);
	const [reviewError, setReviewError] = useState<string | null>(null);

	async function setReviewStatus(reviewStatus: ReviewStatus) {
		if (reviewStatus === convention.reviewStatus) return;
		setReviewSubmitting(true);
		setReviewError(null);
		try {
			const response =
				await editConventionReviewStatusMemoryGroupsMemoryGroupIdConventionsConventionIdReviewStatusPatch(
					memoryGroupId,
					convention.conventionId,
					{ reviewStatus },
				);
			if (response.status !== 200) {
				setReviewError(
					apiErrorMessage(
						response.data,
						"Could not change the convention review status.",
					),
				);
				return;
			}
			reloadConventions();
		} catch (error) {
			setReviewError(requestErrorMessage(error));
		} finally {
			setReviewSubmitting(false);
		}
	}

	return (
		<article className="border-b px-2 py-2 text-sm">
			<div className="flex flex-wrap items-center gap-1">
				<Badge variant={reviewBadgeVariant(convention.reviewStatus)}>
					{convention.reviewStatus}
				</Badge>
				<Badge variant="secondary">{CATEGORY_LABELS[convention.category]}</Badge>
				<span className="text-xs text-muted-foreground">{convention.creatorType}</span>
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button
							variant="ghost"
							size="icon-sm"
							className="ml-auto"
							aria-label="Convention actions"
							disabled={reviewSubmitting}
						>
							<EllipsisIcon />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end">
						<DropdownMenuItem onSelect={() => setEditOpen(true)}>
							<PencilIcon /> Edit convention
						</DropdownMenuItem>
						<DropdownMenuSub>
							<DropdownMenuSubTrigger>Review status</DropdownMenuSubTrigger>
							<DropdownMenuSubContent>
								<DropdownMenuRadioGroup value={convention.reviewStatus}>
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
			<h3 className="mt-1 font-medium wrap-break-word">{convention.title}</h3>
			<p className="mt-1 whitespace-pre-wrap">{convention.rule}</p>
			{convention.rationale !== null && (
				<p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
					{convention.rationale}
				</p>
			)}
			{editOpen && (
				<ConventionDialog
					memoryGroupId={memoryGroupId}
					convention={convention}
					closeDialog={() => setEditOpen(false)}
					reloadConventions={reloadConventions}
				/>
			)}
			{deleteOpen && (
				<DeleteConventionDialog
					memoryGroupId={memoryGroupId}
					convention={convention}
					closeDialog={() => setDeleteOpen(false)}
					reloadConventionsAfterDelete={reloadConventionsAfterDelete}
				/>
			)}
		</article>
	);
}
