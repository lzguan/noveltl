import {
	Combobox,
	ComboboxCollection,
	ComboboxContent,
	ComboboxEmpty,
	ComboboxInput,
	ComboboxItem,
	ComboboxList,
} from "@/components/ui/combobox";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import type { ReactNode } from "react";
import type { Loadable } from "../../lib/loadable";

export interface SearchSelectorProps<T> {
	id: string;
	label: string;
	keyword: string;
	results: Loadable<readonly T[]>;
	selectedResult: T | null;
	placeholder: string;
	emptyMessage: string;
	disabled?: boolean;
	getResultKey: (result: T) => string;
	getResultLabel: (result: T) => string;
	renderResult?: (result: T) => ReactNode;
	setSearchKeyword: (keyword: string) => void;
	selectSearchResult: (result: T | null) => void;
}

export function SearchSelector<T>(props: SearchSelectorProps<T>) {
	const fetchedResults = props.results.status === "ready" ? props.results.data : [];
	const selectedKey =
		props.selectedResult === null ? null : props.getResultKey(props.selectedResult);
	const selectedIsFetched =
		selectedKey !== null &&
		fetchedResults.some((result) => props.getResultKey(result) === selectedKey);
	const items =
		props.selectedResult && !selectedIsFetched
			? [props.selectedResult, ...fetchedResults]
			: fetchedResults;
	const error = props.results.status === "error" ? props.results.message : null;

	return (
		<Field data-invalid={error !== null}>
			<FieldLabel htmlFor={props.id}>{props.label}</FieldLabel>
			<Combobox
				items={items}
				value={props.selectedResult}
				inputValue={props.keyword}
				onInputValueChange={props.setSearchKeyword}
				onValueChange={props.selectSearchResult}
				itemToStringLabel={props.getResultLabel}
				isItemEqualToValue={(item, value) =>
					props.getResultKey(item) === props.getResultKey(value)
				}
				disabled={props.disabled}
			>
				<ComboboxInput
					id={props.id}
					className="w-full"
					placeholder={
						props.results.status === "loading" ? "Loading…" : props.placeholder
					}
					showClear
					aria-invalid={error !== null}
				/>
				<ComboboxContent>
					<ComboboxEmpty>
						{props.results.status === "loading" ? "Loading…" : props.emptyMessage}
					</ComboboxEmpty>
					<ComboboxList>
						<ComboboxCollection>
							{(item: T) => (
								<ComboboxItem key={props.getResultKey(item)} value={item}>
									{props.renderResult?.(item) ?? props.getResultLabel(item)}
								</ComboboxItem>
							)}
						</ComboboxCollection>
					</ComboboxList>
				</ComboboxContent>
			</Combobox>
			<FieldError>{error}</FieldError>
		</Field>
	);
}
