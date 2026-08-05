import { useRef, useState } from "react";

import { createChaptersByUploadChaptersUploadPost } from "@/api/endpoints/default/default";
import type { Novel } from "@/api/models";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { AlertCircleIcon, CheckCircleIcon } from "lucide-react";
import { parseChapterUploadV1, type ChapterUploadSummary } from "./chapterUploadFile";

type UploadChaptersDialogProps = {
	novels: Novel[];
	onOpenChange: (open: boolean) => void;
	open: boolean;
};

function UploadSummary({ file, summary }: { file: File; summary: ChapterUploadSummary }) {
	return (
		<Card>
			<CardHeader>
				<CardTitle className="truncate">{file.name}</CardTitle>
				<CardDescription>V1 JSON chapter upload</CardDescription>
			</CardHeader>
			<CardContent>
				<dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
					<div className="flex flex-col gap-1">
						<dt className="text-muted-foreground">Chapters</dt>
						<dd className="font-medium">{summary.chapterCount}</dd>
					</div>
					<div className="flex flex-col gap-1">
						<dt className="text-muted-foreground">Range</dt>
						<dd className="font-medium">
							{summary.minChapterNum}–{summary.maxChapterNum}
						</dd>
					</div>
					<div className="flex flex-col gap-1">
						<dt className="text-muted-foreground">Public</dt>
						<dd className="font-medium">{summary.publicCount}</dd>
					</div>
					<div className="flex flex-col gap-1">
						<dt className="text-muted-foreground">Draft</dt>
						<dd className="font-medium">{summary.draftCount}</dd>
					</div>
				</dl>
			</CardContent>
		</Card>
	);
}

function UploadChaptersDialog({ novels, open, onOpenChange }: UploadChaptersDialogProps) {
	const [file, setFile] = useState<File | null>(null);
	const [fileError, setFileError] = useState<string | null>(null);
	const [fileInputKey, setFileInputKey] = useState(0);
	const [isParsing, setIsParsing] = useState(false);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [selectedNovelId, setSelectedNovelId] = useState("");
	const [submitError, setSubmitError] = useState<string | null>(null);
	const [successCount, setSuccessCount] = useState<number | null>(null);
	const [summary, setSummary] = useState<ChapterUploadSummary | null>(null);
	const parsingFileRef = useRef<File | null>(null);

	function resetDialog() {
		parsingFileRef.current = null;
		setFile(null);
		setFileError(null);
		setFileInputKey((current) => current + 1);
		setIsParsing(false);
		setSelectedNovelId("");
		setSubmitError(null);
		setSuccessCount(null);
		setSummary(null);
	}

	function handleOpenChange(nextOpen: boolean) {
		if (isSubmitting) return;
		if (!nextOpen) resetDialog();
		onOpenChange(nextOpen);
	}

	async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
		const selectedFile = event.currentTarget.files?.[0] ?? null;
		parsingFileRef.current = selectedFile;
		setFile(selectedFile);
		setFileError(null);
		setSubmitError(null);
		setSummary(null);

		if (selectedFile === null) {
			setIsParsing(false);
			return;
		}

		setIsParsing(true);
		try {
			const result = parseChapterUploadV1(await selectedFile.text());
			if (parsingFileRef.current !== selectedFile) return;
			if (!result.ok) {
				setFileError(result.error);
				return;
			}
			setSummary(result.summary);
		} catch {
			if (parsingFileRef.current === selectedFile) {
				setFileError("The selected file could not be read.");
			}
		} finally {
			if (parsingFileRef.current === selectedFile) setIsParsing(false);
		}
	}

	async function submit(event: React.SubmitEvent<HTMLFormElement>) {
		event.preventDefault();
		if (file === null || summary === null || selectedNovelId === "") return;

		setIsSubmitting(true);
		setSubmitError(null);
		try {
			const response = await createChaptersByUploadChaptersUploadPost({
				file,
				novelId: selectedNovelId,
				version: "v1",
			});
			if (response.status === 200) {
				setSuccessCount(response.data.length);
				return;
			}

			switch (response.status) {
				case 400:
				case 401:
				case 404:
				case 409:
					setSubmitError(response.data.detail);
					break;
				default:
					setSubmitError("The chapters could not be uploaded. Please try again.");
			}
		} catch {
			setSubmitError("The chapters could not be uploaded. Please try again.");
		} finally {
			setIsSubmitting(false);
		}
	}

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent showCloseButton={!isSubmitting} className="sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Upload chapters</DialogTitle>
					<DialogDescription>
						Select a novel and a V1 JSON file. All chapters will be created together.
					</DialogDescription>
				</DialogHeader>

				{successCount !== null ? (
					<>
						<Alert>
							<CheckCircleIcon />
							<AlertTitle>Chapters uploaded</AlertTitle>
							<AlertDescription>
								{successCount}{" "}
								{successCount === 1 ? "chapter was" : "chapters were"} created
								successfully.
							</AlertDescription>
						</Alert>
						<DialogFooter>
							<Button type="button" onClick={() => handleOpenChange(false)}>
								Done
							</Button>
						</DialogFooter>
					</>
				) : (
					<form className="flex flex-col gap-6" onSubmit={submit}>
						{submitError !== null && (
							<Alert variant="destructive">
								<AlertCircleIcon />
								<AlertTitle>Could not upload chapters</AlertTitle>
								<AlertDescription>{submitError}</AlertDescription>
							</Alert>
						)}

						<FieldGroup>
							<Field data-disabled={isSubmitting}>
								<FieldLabel htmlFor="chapter-upload-novel">Novel</FieldLabel>
								<Select
									disabled={isSubmitting}
									value={selectedNovelId}
									onValueChange={setSelectedNovelId}
								>
									<SelectTrigger id="chapter-upload-novel" className="w-full">
										<SelectValue placeholder="Select a novel" />
									</SelectTrigger>
									<SelectContent position="popper">
										<SelectGroup>
											{novels.map((novel) => (
												<SelectItem
													key={novel.novelId}
													value={novel.novelId}
												>
													{novel.novelTitle}
												</SelectItem>
											))}
										</SelectGroup>
									</SelectContent>
								</Select>
							</Field>

							<Field data-disabled={isSubmitting} data-invalid={fileError !== null}>
								<FieldLabel htmlFor="chapter-upload-file">Chapter file</FieldLabel>
								<Input
									key={fileInputKey}
									accept=".json,application/json"
									aria-invalid={fileError !== null}
									disabled={isSubmitting}
									id="chapter-upload-file"
									type="file"
									onChange={handleFileChange}
								/>
								<FieldDescription>
									Choose a V1 JSON document containing between 1 and 10,000
									chapters.
								</FieldDescription>
								{fileError !== null && <FieldError>{fileError}</FieldError>}
							</Field>
						</FieldGroup>

						{file !== null && summary !== null && (
							<UploadSummary file={file} summary={summary} />
						)}

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
								disabled={
									isParsing ||
									isSubmitting ||
									file === null ||
									summary === null ||
									selectedNovelId === ""
								}
							>
								{isParsing
									? "Reading file..."
									: isSubmitting
										? "Uploading..."
										: "Upload chapters"}
							</Button>
						</DialogFooter>
					</form>
				)}
			</DialogContent>
		</Dialog>
	);
}

export { UploadChaptersDialog };
