import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { CONVENTION_CATEGORY_OPTIONS, isConventionCategory } from "@/memory/conventionCategories";
import { useConventions } from "@/memory/hooks/useConventions";
import { PlusIcon, RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { ConventionDialog } from "./ConventionDialog";
import { ConventionRow } from "./ConventionRow";
import { PageNavigation } from "./PageNavigation";

const ALL_CATEGORIES = "all";

export function ConventionsBrowser({ memoryGroupId }: { memoryGroupId: string }) {
	const browser = useConventions(memoryGroupId);
	const [createOpen, setCreateOpen] = useState(false);

	useEffect(() => {
		// Mounting this keyed browser establishes a new group query context.
		// Filter and pagination changes issue their requests directly from events.
		browser.loadConventions();
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	return (
		<div className="flex min-h-0 flex-1 flex-col">
			<div className="flex flex-wrap items-center justify-between gap-3 border-b p-2">
				<div className="flex items-center gap-2">
					<Label
						htmlFor="convention-category-filter"
						className="text-xs text-muted-foreground"
					>
						Category
					</Label>
					<Select
						value={browser.category ?? ALL_CATEGORIES}
						onValueChange={(value) => {
							if (value === ALL_CATEGORIES) browser.setCategory(null);
							else if (isConventionCategory(value)) browser.setCategory(value);
						}}
					>
						<SelectTrigger id="convention-category-filter" size="sm" className="w-40">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value={ALL_CATEGORIES}>All categories</SelectItem>
							{CONVENTION_CATEGORY_OPTIONS.map((option) => (
								<SelectItem key={option.value} value={option.value}>
									{option.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
				<div className="flex items-center gap-2">
					<Button variant="ghost" size="sm" onClick={() => setCreateOpen(true)}>
						<PlusIcon /> New convention
					</Button>
					<Button
						variant="ghost"
						size="icon-sm"
						aria-label="Refresh conventions"
						title="Refresh conventions"
						disabled={browser.conventions.status === "loading"}
						onClick={browser.reloadConventions}
					>
						<RefreshCwIcon />
					</Button>
				</div>
			</div>

			{browser.conventions.status === "idle" || browser.conventions.status === "loading" ? (
				<div aria-busy="true" className="flex flex-col gap-2 p-2">
					<Skeleton className="h-20 w-full" />
					<Skeleton className="h-20 w-full" />
				</div>
			) : browser.conventions.status === "error" ? (
				<div className="flex flex-col items-start gap-2 p-3 text-sm text-destructive">
					<p>{browser.conventions.message}</p>
					<Button variant="outline" size="sm" onClick={browser.reloadConventions}>
						Retry
					</Button>
				</div>
			) : browser.conventions.data.items.length === 0 ? (
				<Empty>
					<EmptyHeader>
						<EmptyTitle>No conventions</EmptyTitle>
						<EmptyDescription>
							Add naming or style guidance that applies across this novel.
						</EmptyDescription>
					</EmptyHeader>
				</Empty>
			) : (
				<div className="flex min-h-0 flex-1 flex-col">
					<div className="min-h-0 flex-1 overflow-y-auto">
						{browser.conventions.data.items.map((convention) => (
							<ConventionRow
								key={convention.conventionId}
								memoryGroupId={memoryGroupId}
								convention={convention}
								reloadConventions={browser.reloadConventions}
								reloadConventionsAfterDelete={browser.reloadConventionsAfterDelete}
							/>
						))}
					</div>
					<PageNavigation
						start={browser.conventions.data.start}
						end={browser.conventions.data.end}
						total={browser.conventions.data.total}
						hasPrevious={browser.conventions.data.hasPrevious}
						hasNext={browser.conventions.data.hasNext}
						onPrevious={browser.loadPreviousPage}
						onNext={browser.loadNextPage}
					/>
				</div>
			)}
			{createOpen && (
				<ConventionDialog
					memoryGroupId={memoryGroupId}
					convention={null}
					closeDialog={() => setCreateOpen(false)}
					reloadConventions={browser.reloadConventions}
				/>
			)}
		</div>
	);
}
