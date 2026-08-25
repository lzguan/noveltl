import type { GlossaryTerm, Memory, ReviewStatus } from "@/api/models";
import { Badge } from "@/components/ui/badge";

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
	memory,
	terms = [],
}: {
	memory: Memory;
	terms?: readonly GlossaryTerm[];
}) {
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
			</div>
			<div
				className={terms.length === 0 ? "mt-1" : "mt-2 grid gap-2 sm:grid-cols-[1fr_auto]"}
			>
				<p className="whitespace-pre-wrap">{memory.memoryContent}</p>
				{terms.length > 0 && (
					<div
						className="flex max-w-32 flex-wrap content-start gap-1"
						aria-label="Associated terms"
					>
						{terms.map((term) => (
							<Badge key={term.termId} variant="outline">
								{term.term}
							</Badge>
						))}
					</div>
				)}
			</div>
		</article>
	);
}
