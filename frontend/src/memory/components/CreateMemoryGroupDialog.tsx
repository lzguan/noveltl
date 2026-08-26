import {
	addMemoryGroupMemoryGroupsPost,
	readAllLanguagesLanguagesGet,
} from "@/api/endpoints/default/default";
import type { CreateMemoryGroup, Language, MemoryGroup } from "@/api/models";
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
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { apiErrorMessage, requestErrorMessage } from "@/lib/apiErrors";
import { AlertCircleIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";

export function CreateMemoryGroupDialog({
	novelId,
	closeDialog,
	addMemoryGroup,
}: {
	novelId: string;
	closeDialog: () => void;
	addMemoryGroup: (group: MemoryGroup) => void;
}) {
	const [languages, setLanguages] = useState<readonly Language[]>([]);
	const [languagesError, setLanguagesError] = useState<string | null>(null);
	const [submitError, setSubmitError] = useState<string | null>(null);
	const {
		control,
		formState: { errors, isSubmitting },
		handleSubmit,
		register,
	} = useForm<{ memoryGroupName: string; memoryLanguage: string }>({
		defaultValues: { memoryGroupName: "", memoryLanguage: "" },
	});

	useEffect(() => {
		const controller = new AbortController();
		void readAllLanguagesLanguagesGet({ signal: controller.signal })
			.then((response) => {
				if (!controller.signal.aborted) setLanguages(response.data);
			})
			.catch((error: unknown) => {
				if (!controller.signal.aborted) setLanguagesError(requestErrorMessage(error));
			});
		return () => controller.abort();
	}, []);

	function handleOpenChange(nextOpen: boolean) {
		if (!nextOpen && !isSubmitting) closeDialog();
	}

	async function submit(values: { memoryGroupName: string; memoryLanguage: string }) {
		setSubmitError(null);
		const payload: CreateMemoryGroup = {
			memoryGroupName: values.memoryGroupName.trim(),
			memoryLanguage: values.memoryLanguage,
			novelId,
		};
		try {
			const response = await addMemoryGroupMemoryGroupsPost(payload);
			if (response.status !== 200) {
				setSubmitError(
					apiErrorMessage(response.data, "Could not create the memory group."),
				);
				return;
			}
			addMemoryGroup(response.data);
			closeDialog();
		} catch (error) {
			setSubmitError(requestErrorMessage(error));
		}
	}

	const languagesLoading = languages.length === 0 && languagesError === null;

	return (
		<Dialog open onOpenChange={handleOpenChange}>
			<DialogContent showCloseButton={!isSubmitting}>
				<DialogHeader>
					<DialogTitle>Create memory group</DialogTitle>
					<DialogDescription>
						Create a collection of memories for this novel and language.
					</DialogDescription>
				</DialogHeader>
				<form className="flex flex-col gap-6" onSubmit={handleSubmit(submit)}>
					{submitError !== null && (
						<Alert variant="destructive">
							<AlertCircleIcon />
							<AlertTitle>Could not create the memory group</AlertTitle>
							<AlertDescription>{submitError}</AlertDescription>
						</Alert>
					)}
					<FieldGroup>
						<Field data-invalid={Boolean(errors.memoryGroupName)}>
							<FieldLabel htmlFor="create-memory-group-name">Name</FieldLabel>
							<Input
								id="create-memory-group-name"
								disabled={isSubmitting}
								aria-invalid={Boolean(errors.memoryGroupName)}
								maxLength={100}
								{...register("memoryGroupName", {
									required: "Name is required.",
									validate: (value) =>
										value.trim().length > 0 || "Name is required.",
								})}
							/>
							<FieldError errors={[errors.memoryGroupName]} />
						</Field>
						<Field data-invalid={Boolean(errors.memoryLanguage)}>
							<FieldLabel htmlFor="create-memory-group-language">Language</FieldLabel>
							<Controller
								control={control}
								name="memoryLanguage"
								rules={{ required: "Language is required." }}
								render={({ field }) => (
									<Select
										value={field.value}
										onValueChange={field.onChange}
										disabled={
											isSubmitting ||
											languagesLoading ||
											languagesError !== null
										}
									>
										<SelectTrigger
											id="create-memory-group-language"
											className="w-full"
										>
											<SelectValue
												placeholder={
													languagesError !== null
														? "Languages unavailable"
														: languagesLoading
															? "Loading languages…"
															: "Select language"
												}
											/>
										</SelectTrigger>
										<SelectContent>
											{languages.map((language) => (
												<SelectItem
													key={language.languageCode}
													value={language.languageCode}
												>
													{language.languageName}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								)}
							/>
							{languagesError !== null && <FieldError>{languagesError}</FieldError>}
							<FieldError errors={[errors.memoryLanguage]} />
						</Field>
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
							disabled={isSubmitting || languagesLoading || languagesError !== null}
						>
							{isSubmitting ? "Creating…" : "Create memory group"}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
