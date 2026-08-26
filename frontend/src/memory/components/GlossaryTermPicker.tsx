import type { GlossaryTerm } from "@/api/models";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useGlossaryTerms } from "@/memory/hooks/useGlossaryTerms";
import { XIcon } from "lucide-react";
import { useEffect } from "react";
import { PageNavigation } from "./PageNavigation";

export function GlossaryTermPicker({
	memoryGroupId,
	selectedTerms,
	disabled,
	setTermSelected,
}: {
	memoryGroupId: string;
	selectedTerms: readonly GlossaryTerm[];
	disabled: boolean;
	setTermSelected: (term: GlossaryTerm, selected: boolean) => void;
}) {
	const picker = useGlossaryTerms(memoryGroupId, null);

	useEffect(() => {
		// This picker always searches the complete memory-group glossary.
		picker.setShowAllTerms(true);
		// oxlint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	return (
		<div className="flex flex-col gap-2">
			<div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-md border border-input px-2 py-1.5">
				{selectedTerms.map((term) => (
					<span
						key={term.termId}
						className="flex items-center gap-1 rounded-sm bg-muted px-1.5 py-0.5 text-xs font-medium"
					>
						{term.term}
						<Button
							type="button"
							variant="ghost"
							size="icon-xs"
							className="-mr-1 size-5"
							aria-label={`Remove ${term.term}`}
							disabled={disabled}
							onClick={() => setTermSelected(term, false)}
						>
							<XIcon />
						</Button>
					</span>
				))}
				<Input
					className="h-7 min-w-36 flex-1 border-0 px-1 shadow-none focus-visible:ring-0"
					aria-label="Search for another term"
					placeholder="Search for another term…"
					value={picker.search}
					disabled={disabled}
					onChange={(event) => picker.setSearch(event.target.value)}
				/>
			</div>

			{picker.terms.status === "idle" || picker.terms.status === "loading" ? (
				<div aria-busy="true" className="flex flex-col gap-1 rounded-md border p-2">
					<Skeleton className="h-7 w-full" />
					<Skeleton className="h-7 w-full" />
				</div>
			) : picker.terms.status === "error" ? (
				<div className="flex items-center justify-between gap-2 text-xs text-destructive">
					<span>{picker.terms.message}</span>
					<Button type="button" variant="outline" size="sm" onClick={picker.reloadTerms}>
						Retry
					</Button>
				</div>
			) : picker.terms.data.items.length === 0 ? (
				<p className="rounded-md border p-2 text-xs text-muted-foreground">
					No matching terms.
				</p>
			) : (
				<div className="rounded-md border">
					<div className="max-h-40 overflow-y-auto p-1">
						{picker.terms.data.items.map((term) => {
							const selected = selectedTerms.some(
								(candidate) => candidate.termId === term.termId,
							);
							return (
								<label
									key={term.termId}
									className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
								>
									<Checkbox
										checked={selected}
										disabled={disabled}
										onCheckedChange={(checked) =>
											setTermSelected(term, checked === true)
										}
									/>
									<span className="min-w-0 flex-1 truncate">{term.term}</span>
								</label>
							);
						})}
					</div>
					{!disabled && (
						<PageNavigation
							start={picker.terms.data.start}
							end={picker.terms.data.end}
							total={picker.terms.data.total}
							hasPrevious={picker.terms.data.hasPrevious}
							hasNext={picker.terms.data.hasNext}
							onPrevious={picker.loadPreviousPage}
							onNext={picker.loadNextPage}
						/>
					)}
				</div>
			)}
		</div>
	);
}
