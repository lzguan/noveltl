import { useState } from "react";
import { Controller, type Control, type UseFormSetValue } from "react-hook-form";

import { readSourceWorksSourceWorksGet } from "@/api/endpoints/default/default";
import type { SourceWork } from "@/api/models";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import {
	InputGroup,
	InputGroupAddon,
	InputGroupButton,
	InputGroupInput,
} from "@/components/ui/input-group";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { SearchIcon } from "lucide-react";
import type { CreateNovelFormValues } from "./createNovelForm";

type SourceWorkSearchFieldProps = {
	control: Control<CreateNovelFormValues>;
	isDisabled: boolean;
	setValue: UseFormSetValue<CreateNovelFormValues>;
};

function SourceWorkSearchField({ control, isDisabled, setValue }: SourceWorkSearchFieldProps) {
	const [searchText, setSearchText] = useState("");
	const [sourceWorks, setSourceWorks] = useState<SourceWork[]>([]);
	const [hasSearched, setHasSearched] = useState(false);
	const [searching, setSearching] = useState(false);
	const [searchError, setSearchError] = useState(false);

	async function searchSourceWorks() {
		const query = searchText.trim();
		if (!query || searching) return;

		setSearching(true);
		setSearchError(false);
		setHasSearched(false);
		try {
			const response = await readSourceWorksSourceWorksGet({
				retNovels: false,
				titleContains: query,
			});
			if (response.status === 200) {
				setSourceWorks(response.data.map((result) => result.sourceWork));
			} else {
				setSourceWorks([]);
				setSearchError(true);
			}
		} catch {
			setSourceWorks([]);
			setSearchError(true);
		} finally {
			setHasSearched(true);
			setSearching(false);
		}
	}

	return (
		<Field data-invalid={searchError}>
			<FieldLabel htmlFor="create-novel-source-search">Source work</FieldLabel>
			<FieldDescription>
				Optional. If you do not select a match, a source work is created automatically.
			</FieldDescription>
			<InputGroup>
				<InputGroupInput
					id="create-novel-source-search"
					aria-invalid={searchError}
					disabled={isDisabled || searching}
					placeholder="Search source works..."
					value={searchText}
					onChange={(event) => {
						setSearchText(event.target.value);
						setSourceWorks([]);
						setHasSearched(false);
						setSearchError(false);
						setValue("sourceWorkId", null);
					}}
					onKeyDown={(event) => {
						if (event.key === "Enter") {
							event.preventDefault();
							void searchSourceWorks();
						}
					}}
				/>
				<InputGroupAddon align="inline-end">
					<InputGroupButton
						disabled={isDisabled || searching || searchText.trim().length === 0}
						onClick={() => void searchSourceWorks()}
					>
						<SearchIcon data-icon="inline-start" />
						{searching ? "Searching..." : "Search"}
					</InputGroupButton>
				</InputGroupAddon>
			</InputGroup>
			{searchError && <FieldError>Source works could not be searched.</FieldError>}
			{hasSearched && !searchError && sourceWorks.length === 0 && (
				<FieldDescription>No matching source works found.</FieldDescription>
			)}

			{sourceWorks.length > 0 && (
				<Controller
					control={control}
					name="sourceWorkId"
					render={({ field }) => (
						<Select
							disabled={isDisabled}
							onValueChange={field.onChange}
							value={field.value ?? undefined}
						>
							<SelectTrigger aria-label="Source work results" className="w-full">
								<SelectValue placeholder="Select a matching source work" />
							</SelectTrigger>
							<SelectContent>
								<SelectGroup>
									{sourceWorks.map((sourceWork) => (
										<SelectItem
											key={sourceWork.sourceWorkId}
											value={sourceWork.sourceWorkId}
										>
											{sourceWork.sourceWorkTitle}
										</SelectItem>
									))}
								</SelectGroup>
							</SelectContent>
						</Select>
					)}
				/>
			)}
		</Field>
	);
}

export { SourceWorkSearchField };
