import type { DataType, GroupData, LabelRef, TextSpan } from "@/api/models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Popover,
	PopoverContent,
	PopoverHeader,
	PopoverTitle,
	PopoverTrigger,
} from "@/components/ui/popover";
import { Info } from "lucide-react";
import type { TextReference } from "../types";

function shortId(value: string) {
	return value.slice(0, 8);
}

function Metadata({ values }: { values: readonly [string, string | number][] }) {
	return (
		<dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
			{values.map(([label, value]) => (
				<div className="contents" key={label}>
					<dt className="text-muted-foreground">{label}</dt>
					<dd className="min-w-0 break-all">{value}</dd>
				</div>
			))}
		</dl>
	);
}

export function TextSpanCell({
	value,
	openTextReference,
}: {
	value: TextSpan;
	openTextReference?: (reference: TextReference) => void;
}) {
	const openReference = () => openTextReference?.({ type: "textSpan", value });
	return (
		<div className="flex items-center gap-1">
			<Button
				type="button"
				variant="ghost"
				size="xs"
				disabled={!openTextReference}
				onDoubleClick={openReference}
				onClick={(event) => {
					if (event.detail === 0) openReference();
				}}
				title="Double-click to open this text span"
			>
				{shortId(value.chapterId)}:{value.start}–{value.end}
			</Button>
			<Popover>
				<PopoverTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						size="icon-xs"
						aria-label="Text span info"
					>
						<Info />
					</Button>
				</PopoverTrigger>
				<PopoverContent align="start">
					<PopoverHeader>
						<PopoverTitle>Text span</PopoverTitle>
					</PopoverHeader>
					<Metadata
						values={[
							["Chapter", value.chapterId],
							["Content", value.chapterContentId],
							["Range", `${value.start}–${value.end}`],
						]}
					/>
				</PopoverContent>
			</Popover>
		</div>
	);
}

export function LabelCell({
	value,
	openTextReference,
}: {
	value: LabelRef;
	openTextReference?: (reference: TextReference) => void;
}) {
	const openReference = () => openTextReference?.({ type: "labelRef", value });
	return (
		<div className="flex items-center gap-1">
			<Button
				type="button"
				variant="ghost"
				size="xs"
				disabled={!openTextReference}
				onDoubleClick={openReference}
				onClick={(event) => {
					if (event.detail === 0) openReference();
				}}
				title="Double-click to open this label"
			>
				Label {shortId(value.labelId)}
			</Button>
			<Popover>
				<PopoverTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						size="icon-xs"
						aria-label="Label reference info"
					>
						<Info />
					</Button>
				</PopoverTrigger>
				<PopoverContent align="start">
					<PopoverHeader>
						<PopoverTitle>Label reference</PopoverTitle>
					</PopoverHeader>
					<Metadata
						values={[
							["Label", value.labelId],
							["Label data", value.labelDataId],
							["Label group", value.labelGroupId],
							["Chapter", value.chapterId],
							["Content", value.chapterContentId],
						]}
					/>
				</PopoverContent>
			</Popover>
		</div>
	);
}

export function GroupDataCell({ value }: { value: GroupData | undefined }) {
	if (!value) return <span className="text-muted-foreground">—</span>;
	if (value.type === "bool")
		return <Badge variant="outline">{value.value ? "true" : "false"}</Badge>;
	return <span>{value.value}</span>;
}

export function DataCell({
	value,
	openTextReference,
}: {
	value: DataType | undefined;
	openTextReference?: (reference: TextReference) => void;
}) {
	if (!value) return <span className="text-muted-foreground">—</span>;

	switch (value.type) {
		case "string":
		case "int":
		case "float":
			return <span>{value.value}</span>;
		case "bool":
			return <Badge variant="outline">{value.value ? "true" : "false"}</Badge>;
		case "textSpan":
			return <TextSpanCell value={value.value} openTextReference={openTextReference} />;
		case "labelRef":
			return <LabelCell value={value.value} openTextReference={openTextReference} />;
	}
}
