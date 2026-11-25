import { useState } from "react";
import { Globe, Link2, Lock, Shield, type LucideIcon } from "lucide-react";
import { updateNovelNovelsNovelIdPatch } from "@/api/endpoints/default/default";
import { Visibility } from "@/api/models";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { cn } from "@/lib/utils";

export type VisibilityMeta = {
	value: Visibility;
	label: string;
	description: string;
	icon: LucideIcon;
};

export const VISIBILITY_OPTIONS: readonly VisibilityMeta[] = [
	{
		value: Visibility.NUMBER_0,
		label: "Private",
		description: "Only contributors can access this novel.",
		icon: Lock,
	},
	{
		value: Visibility.NUMBER_1,
		label: "Restricted",
		description: "Contributors only (restricted access).",
		icon: Shield,
	},
	{
		value: Visibility.NUMBER_2,
		label: "Unlisted",
		description: "Anyone with the link can read public chapters; hidden from listings.",
		icon: Link2,
	},
	{
		value: Visibility.NUMBER_3,
		label: "Public",
		description: "Listed publicly; anyone can read public chapters.",
		icon: Globe,
	},
];

export function getVisibilityMeta(visibility: Visibility): VisibilityMeta {
	return (
		VISIBILITY_OPTIONS.find((option) => option.value === visibility) ?? VISIBILITY_OPTIONS[0]
	);
}

export function NovelVisibilityDialog({
	novelId,
	currentVisibility,
	publicChapterCount,
	totalChapterCount,
	onUpdated,
	onClose,
}: {
	novelId: string;
	currentVisibility: Visibility;
	publicChapterCount: number;
	totalChapterCount: number;
	onUpdated: (visibility: Visibility) => void;
	onClose: () => void;
}) {
	const [selected, setSelected] = useState<Visibility>(currentVisibility);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleSave = async () => {
		if (submitting || selected === currentVisibility) return;
		setSubmitting(true);
		setError(null);
		try {
			const resp = await updateNovelNovelsNovelIdPatch(novelId, {
				novelVisibility: selected,
			});
			if (resp.status !== 200) {
				setError(apiErrorMessage(resp.data, "Could not update novel visibility."));
				return;
			}
			onUpdated(resp.data.novelVisibility);
			onClose();
		} catch (err: unknown) {
			setError(requestErrorMessage(err));
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<Dialog
			open
			onOpenChange={(open) => {
				if (!open) onClose();
			}}
		>
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<DialogTitle>Novel visibility</DialogTitle>
					<DialogDescription>
						Choose who can discover and read this novel.
					</DialogDescription>
				</DialogHeader>
				<div
					role="radiogroup"
					aria-label="Novel visibility"
					className="flex flex-col gap-1.5"
				>
					{VISIBILITY_OPTIONS.map((option) => {
						const Icon = option.icon;
						const checked = selected === option.value;
						return (
							<button
								key={option.value}
								type="button"
								role="radio"
								aria-checked={checked}
								disabled={submitting}
								className={cn(
									"flex cursor-pointer items-start gap-2.5 rounded-md border px-3 py-2 text-left text-xs",
									checked
										? "border-primary bg-accent/60 text-foreground"
										: "border-border text-muted-foreground hover:bg-accent/30 hover:text-foreground",
								)}
								onClick={() => setSelected(option.value)}
							>
								<Icon className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
								<div className="min-w-0 flex-1">
									<div className="font-medium text-foreground">
										{option.label}
									</div>
									<div className="text-muted-foreground">
										{option.description}
									</div>
								</div>
							</button>
						);
					})}
				</div>
				<p className="text-xs text-muted-foreground">
					Currently {publicChapterCount} of {totalChapterCount} chapters are public.
				</p>
				{error !== null && (
					<p role="alert" className="text-xs text-destructive">
						{error}
					</p>
				)}
				<DialogFooter>
					<Button type="button" variant="outline" onClick={onClose}>
						Cancel
					</Button>
					<Button
						type="button"
						disabled={submitting || selected === currentVisibility}
						onClick={() => void handleSave()}
					>
						{submitting ? "Saving..." : "Save"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
