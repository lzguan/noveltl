import { Controller, type Control, type FieldErrors, type UseFormRegister } from "react-hook-form";

import { NovelType, Visibility, type Language } from "@/api/models";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
	novelTypeFromValue,
	visibilityFromValue,
	type CreateNovelFormValues,
} from "./createNovelForm";

type NovelMetadataFieldsProps = {
	control: Control<CreateNovelFormValues>;
	errors: FieldErrors<CreateNovelFormValues>;
	isDisabled: boolean;
	languages: Language[];
	languagesError: boolean;
	loadingLanguages: boolean;
	register: UseFormRegister<CreateNovelFormValues>;
};

function NovelMetadataFields({
	control,
	errors,
	isDisabled,
	languages,
	languagesError,
	loadingLanguages,
	register,
}: NovelMetadataFieldsProps) {
	return (
		<FieldGroup className="grid gap-5 sm:grid-cols-2">
			<Field className="sm:col-span-2" data-invalid={Boolean(errors.novelTitle)}>
				<FieldLabel htmlFor="create-novel-title">Title</FieldLabel>
				<Input
					id="create-novel-title"
					aria-invalid={Boolean(errors.novelTitle)}
					disabled={isDisabled}
					maxLength={255}
					{...register("novelTitle", {
						maxLength: {
							message: "Title must be 255 characters or fewer.",
							value: 255,
						},
						required: "Title is required.",
						validate: (value) => value.trim().length > 0 || "Title is required.",
					})}
				/>
				<FieldError errors={[errors.novelTitle]} />
			</Field>

			<Field data-invalid={Boolean(errors.novelAuthor)}>
				<FieldLabel htmlFor="create-novel-author">Author</FieldLabel>
				<Input
					id="create-novel-author"
					aria-invalid={Boolean(errors.novelAuthor)}
					disabled={isDisabled}
					maxLength={31}
					{...register("novelAuthor", {
						maxLength: { message: "Author must be 31 characters or fewer.", value: 31 },
					})}
				/>
				<FieldError errors={[errors.novelAuthor]} />
			</Field>

			<Field data-invalid={Boolean(errors.languageCode)}>
				<FieldLabel htmlFor="create-novel-language">Language</FieldLabel>
				<Controller
					control={control}
					name="languageCode"
					rules={{ required: "Language is required." }}
					render={({ field }) => (
						<Select
							disabled={isDisabled || loadingLanguages || languagesError}
							onValueChange={field.onChange}
							value={field.value || undefined}
						>
							<SelectTrigger
								id="create-novel-language"
								aria-invalid={Boolean(errors.languageCode)}
								className="w-full"
							>
								<SelectValue
									placeholder={
										loadingLanguages
											? "Loading languages..."
											: "Select language"
									}
								/>
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									{languages.map((language) => (
										<SelectItem
											key={language.languageCode}
											value={language.languageCode}
										>
											{language.languageName}
										</SelectItem>
									))}
								</SelectGroup>
							</SelectContent>
						</Select>
					)}
				/>
				{languagesError && <FieldError>Languages could not be loaded.</FieldError>}
				<FieldError errors={[errors.languageCode]} />
			</Field>

			<Field>
				<FieldLabel htmlFor="create-novel-type">Type</FieldLabel>
				<Controller
					control={control}
					name="novelType"
					render={({ field }) => (
						<Select
							disabled={isDisabled}
							onValueChange={(value) => field.onChange(novelTypeFromValue(value))}
							value={field.value}
						>
							<SelectTrigger id="create-novel-type" className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectItem value={NovelType.original}>Original</SelectItem>
									<SelectItem value={NovelType.translation}>
										Translation
									</SelectItem>
									<SelectItem value={NovelType.other}>Other</SelectItem>
								</SelectGroup>
							</SelectContent>
						</Select>
					)}
				/>
			</Field>

			<Field>
				<FieldLabel htmlFor="create-novel-visibility">Visibility</FieldLabel>
				<Controller
					control={control}
					name="novelVisibility"
					render={({ field }) => (
						<Select
							disabled={isDisabled}
							onValueChange={(value) => field.onChange(visibilityFromValue(value))}
							value={String(field.value)}
						>
							<SelectTrigger id="create-novel-visibility" className="w-full">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									<SelectItem value={String(Visibility.NUMBER_0)}>
										Private
									</SelectItem>
									<SelectItem value={String(Visibility.NUMBER_1)}>
										Restricted
									</SelectItem>
									<SelectItem value={String(Visibility.NUMBER_2)}>
										Unlisted
									</SelectItem>
									<SelectItem value={String(Visibility.NUMBER_3)}>
										Public
									</SelectItem>
								</SelectGroup>
							</SelectContent>
						</Select>
					)}
				/>
			</Field>

			<Field className="sm:col-span-2">
				<FieldLabel htmlFor="create-novel-description">Description</FieldLabel>
				<Textarea
					id="create-novel-description"
					disabled={isDisabled}
					rows={4}
					{...register("novelDescription")}
				/>
			</Field>
		</FieldGroup>
	);
}

export { NovelMetadataFields };
