import type { GlossaryMemory } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { LinkIcon } from "lucide-react";
import { EditMemoryTermsDialog } from "./EditMemoryTermsDialog";
import { MemoryRow } from "./MemoryRow";

export function GlossaryMemoryRow({
	memoryGroupId,
	glossaryMemory,
	chapterId,
	chapterNum,
	reloadMemories,
	reloadMemoriesAfterDelete,
	reloadTerms,
}: {
	memoryGroupId: string;
	glossaryMemory: GlossaryMemory;
	chapterId: string | null;
	chapterNum: number | null;
	reloadMemories: () => void;
	reloadMemoriesAfterDelete: () => void;
	reloadTerms: () => void;
}) {
	return (
		<MemoryRow
			memoryGroupId={memoryGroupId}
			memory={glossaryMemory.memory}
			additionalData={glossaryMemory.terms}
			renderAdditionalContent={(terms) =>
				terms.length > 0 ? (
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
				) : null
			}
			additionalDropdownOptions={[
				{
					key: "edit-associated-terms",
					renderDropdownItem: (openDialog) => (
						<DropdownMenuItem onSelect={openDialog}>
							<LinkIcon /> Edit associated terms
						</DropdownMenuItem>
					),
					renderDialog: ({
						memoryGroupId,
						memory,
						additionalData,
						closeDialog,
						reloadMemories,
					}) => (
						<EditMemoryTermsDialog
							memoryGroupId={memoryGroupId}
							memory={memory}
							terms={additionalData}
							closeDialog={closeDialog}
							reloadMemories={reloadMemories}
							reloadTerms={reloadTerms}
						/>
					),
				},
			]}
			reloadAdditionalData={reloadTerms}
			chapterId={chapterId}
			chapterNum={chapterNum}
			reloadMemories={reloadMemories}
			reloadMemoriesAfterDelete={reloadMemoriesAfterDelete}
		/>
	);
}
