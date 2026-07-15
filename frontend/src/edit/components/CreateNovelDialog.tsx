import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import {
	createNovelNovelsPost,
	readAllLanguagesLanguagesGet,
} from "@/api/endpoints/default/default";
import type { CreateNovel, Language, Novel } from "@/api/models";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { FieldGroup } from "@/components/ui/field";
import { AlertCircleIcon } from "lucide-react";
import { NovelMetadataFields } from "./NovelMetadataFields";
import { SourceWorkSearchField } from "./SourceWorkSearchField";
import { createNovelDefaultValues, type CreateNovelFormValues } from "./createNovelForm";

type CreateNovelDialogProps = {
	onCreated: (novel: Novel) => void;
	onOpenChange: (open: boolean) => void;
	open: boolean;
};

function CreateNovelDialog({ open, onOpenChange, onCreated }: CreateNovelDialogProps) {
	const [languages, setLanguages] = useState<Language[]>([]);
	const [languagesError, setLanguagesError] = useState(false);
	const [loadingLanguages, setLoadingLanguages] = useState(false);
	const [submitError, setSubmitError] = useState(false);

	const {
		control,
		formState: { errors, isSubmitting },
		handleSubmit,
		register,
		reset,
		setValue,
	} = useForm<CreateNovelFormValues>({ defaultValues: createNovelDefaultValues });

	useEffect(() => {
		if (!open || languages.length > 0) return;

		let ignore = false;
		setLanguagesError(false);
		setLoadingLanguages(true);
		readAllLanguagesLanguagesGet()
			.then((response) => {
				if (!ignore) setLanguages(response.data);
			})
			.catch(() => {
				if (!ignore) setLanguagesError(true);
			})
			.finally(() => {
				if (!ignore) setLoadingLanguages(false);
			});

		return () => {
			ignore = true;
		};
	}, [languages.length, open]);

	function clearDialog() {
		reset(createNovelDefaultValues);
		setSubmitError(false);
	}

	function handleOpenChange(nextOpen: boolean) {
		if (isSubmitting) return;
		if (!nextOpen) clearDialog();
		onOpenChange(nextOpen);
	}

	async function submit(values: CreateNovelFormValues) {
		setSubmitError(false);
		const payload: CreateNovel = {
			languageCode: values.languageCode,
			novelAuthor: values.novelAuthor.trim() || null,
			novelDescription: values.novelDescription.trim() || null,
			novelTitle: values.novelTitle.trim(),
			novelType: values.novelType,
			novelVisibility: values.novelVisibility,
			sourceWorkId: values.sourceWorkId,
		};

		try {
			const response = await createNovelNovelsPost(payload);
			if (response.status !== 200) {
				setSubmitError(true);
				return;
			}
			onCreated(response.data);
			clearDialog();
			onOpenChange(false);
		} catch {
			setSubmitError(true);
		}
	}

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent
				className="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-2xl"
				showCloseButton={!isSubmitting}
			>
				<DialogHeader>
					<DialogTitle>Create novel</DialogTitle>
					<DialogDescription>
						Add a novel to your edit workspace. You can begin adding chapters afterward.
					</DialogDescription>
				</DialogHeader>

				<form className="flex flex-col gap-6" onSubmit={handleSubmit(submit)}>
					{submitError && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertTitle>Could not create the novel.</AlertTitle>
							<AlertDescription>
								Check the form and try again. Your entries have been preserved.
							</AlertDescription>
						</Alert>
					)}

					<NovelMetadataFields
						control={control}
						errors={errors}
						isDisabled={isSubmitting}
						languages={languages}
						languagesError={languagesError}
						loadingLanguages={loadingLanguages}
						register={register}
					/>

					<FieldGroup>
						<SourceWorkSearchField
							control={control}
							isDisabled={isSubmitting}
							setValue={setValue}
						/>
					</FieldGroup>

					<DialogFooter>
						<Button
							type="button"
							variant="outline"
							disabled={isSubmitting}
							onClick={() => handleOpenChange(false)}
						>
							Cancel
						</Button>
						<Button
							type="submit"
							disabled={isSubmitting || loadingLanguages || languagesError}
						>
							{isSubmitting ? "Creating..." : "Create novel"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}

export { CreateNovelDialog };
