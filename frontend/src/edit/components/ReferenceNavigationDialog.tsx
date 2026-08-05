import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import type { ReferenceNavigationNotice } from "../hooks/useReferenceNavigation";

export function ReferenceNavigationDialog({
	notice,
	dismissNotice,
}: {
	notice: ReferenceNavigationNotice | null;
	dismissNotice: () => void;
}) {
	const outdated = notice?.kind === "outdated";

	return (
		<Dialog
			open={notice !== null}
			onOpenChange={(open) => {
				if (!open) dismissNotice();
			}}
		>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>
						{outdated
							? "Reference uses an older chapter version"
							: "Reference unavailable"}
					</DialogTitle>
					<DialogDescription>
						{outdated && notice
							? `Chapter ${notice.chapterNum} has changed since this reference was created. The current chapter was opened, but the stored text location could not be highlighted safely.`
							: notice?.chapterNum === null
								? "The chapter for this reference is not available in the editor."
								: `Chapter ${notice?.chapterNum} was opened, but the referenced text could not be located.`}
					</DialogDescription>
				</DialogHeader>
				<DialogFooter showCloseButton />
			</DialogContent>
		</Dialog>
	);
}
