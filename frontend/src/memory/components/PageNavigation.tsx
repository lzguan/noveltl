import { Button } from "@/components/ui/button";

export function PageNavigation({
	start,
	end,
	total,
	hasPrevious,
	hasNext,
	onPrevious,
	onNext,
}: {
	start: number;
	end: number;
	total?: number;
	hasPrevious: boolean;
	hasNext: boolean;
	onPrevious: () => void;
	onNext: () => void;
}) {
	return (
		<nav
			aria-label="Pagination"
			className="flex items-center justify-between gap-2 border-t bg-background p-2"
		>
			<Button variant="outline" size="sm" disabled={!hasPrevious} onClick={onPrevious}>
				Previous
			</Button>
			<span className="text-xs text-muted-foreground">
				{start}–{end}
				{total === undefined ? null : ` of ${total}`}
			</span>
			<Button variant="outline" size="sm" disabled={!hasNext} onClick={onNext}>
				Next
			</Button>
		</nav>
	);
}
