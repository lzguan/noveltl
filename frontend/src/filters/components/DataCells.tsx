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
	openChapter,
}: {
	value: TextSpan;
	openChapter?: (chapterId: string) => void;
}) {
	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button type="button" variant="ghost" size="xs">
					{shortId(value.chapterId)}:{value.start}–{value.end}
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
				{openChapter && (
					<Button type="button" size="sm" onClick={() => openChapter(value.chapterId)}>
						Open chapter
					</Button>
				)}
			</PopoverContent>
		</Popover>
	);
}

export function LabelCell({
	value,
	openChapter,
}: {
	value: LabelRef;
	openChapter?: (chapterId: string) => void;
}) {
	return (
		<Popover>
			<PopoverTrigger asChild>
				<Button type="button" variant="ghost" size="xs">
					Label {shortId(value.labelId)}
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
				{openChapter && (
					<Button type="button" size="sm" onClick={() => openChapter(value.chapterId)}>
						Open chapter
					</Button>
				)}
			</PopoverContent>
		</Popover>
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
	openChapter,
}: {
	value: DataType | undefined;
	openChapter?: (chapterId: string) => void;
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
			return <TextSpanCell value={value.value} openChapter={openChapter} />;
		case "labelRef":
			return <LabelCell value={value.value} openChapter={openChapter} />;
	}
}
