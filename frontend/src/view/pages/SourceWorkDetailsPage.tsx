import {
	readNovelsBySourceWorkSourceWorksSourceWorkIdNovelsGet,
	readSourceWorkSourceWorksSourceWorkIdGet,
} from "@/api/endpoints/default/default";
import type { Novel, SourceWork } from "@/api/models";
import { NovelList } from "@/view/components/NovelList";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { routeTo } from "@/routes";
import { BookOpenIcon, ChevronLeftIcon, LibraryIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

function SourceWorkDetailsSkeleton() {
	return (
		<div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
			<Card>
				<CardHeader>
					<Skeleton className="h-8 w-2/3" />
					<Skeleton className="h-4 w-1/2" />
				</CardHeader>
				<CardContent className="flex flex-col gap-3">
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-3/4" />
				</CardContent>
			</Card>
			<Card size="sm">
				<CardHeader>
					<Skeleton className="h-5 w-24" />
				</CardHeader>
				<CardContent className="flex flex-col gap-3">
					<Skeleton className="h-4 w-full" />
					<Skeleton className="h-4 w-4/5" />
				</CardContent>
			</Card>
		</div>
	);
}

function SourceWorkDetailsPage() {
	const params = useParams();
	const [loading, setLoading] = useState(false);
	const [sourceWork, setSourceWork] = useState<SourceWork | null>(null);
	const [novels, setNovels] = useState<Novel[]>([]);
	const [error, setError] = useState<unknown>(null);

	useEffect(() => {
		let ignore = false;

		async function loadSourceWork() {
			const sourceWorkId = params.sourceWorkId;
			if (!sourceWorkId) {
				setError(new Error("Missing source work id."));
				return;
			}

			setLoading(true);
			setError(null);

			const [sourceWorkResponse, novelsResponse] = await Promise.all([
				readSourceWorkSourceWorksSourceWorkIdGet(sourceWorkId),
				readNovelsBySourceWorkSourceWorksSourceWorkIdNovelsGet(sourceWorkId),
			]);

			if (ignore) {
				return;
			}

			if (sourceWorkResponse.status !== 200) {
				setError(sourceWorkResponse.data);
				setSourceWork(null);
				setNovels([]);
				setLoading(false);
				return;
			}

			setSourceWork(sourceWorkResponse.data);

			if (novelsResponse.status !== 200) {
				setError(novelsResponse.data);
				setNovels([]);
			} else {
				setNovels(novelsResponse.data ?? []);
			}

			setLoading(false);
		}

		loadSourceWork().catch((err) => {
			setError(err);
		});

		return () => {
			ignore = true;
		};
	}, [params.sourceWorkId]);

	return (
		<main>
			<section className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-10">
				<Button asChild variant="ghost" className="w-fit pl-2">
					<Link to={routeTo.view.sourceworks()}>
						<ChevronLeftIcon data-icon="inline-start" />
						Source Works
					</Link>
				</Button>

				{loading ? <SourceWorkDetailsSkeleton /> : null}

				{!loading && error ? (
					<Empty className="border">
						<EmptyHeader>
							<EmptyTitle>Unable to load source work</EmptyTitle>
							<EmptyDescription>
								The source work metadata or related novels could not be loaded.
							</EmptyDescription>
						</EmptyHeader>
					</Empty>
				) : null}

				{!loading && !error && sourceWork ? (
					<>
						<Card>
							<CardHeader>
								<div className="flex min-w-0 items-start gap-4">
									<div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
										<LibraryIcon />
									</div>
									<div className="min-w-0">
										<CardTitle className="text-3xl tracking-tight">
											{sourceWork.sourceWorkTitle}
										</CardTitle>
										<p className="pt-2 text-sm leading-7 text-muted-foreground">
											{sourceWork.sourceWorkDescription ||
												"No description available."}
										</p>
									</div>
								</div>
							</CardHeader>
						</Card>

						<div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
							<div className="flex min-w-0 flex-col gap-6">
								{novels.length > 0 ? (
									<Card>
										<CardHeader>
											<CardTitle>Novels</CardTitle>
										</CardHeader>
										<CardContent>
											<NovelList novels={novels} showDescription />
										</CardContent>
									</Card>
								) : (
									<Empty className="border">
										<EmptyHeader>
											<EmptyTitle>No novels linked</EmptyTitle>
											<EmptyDescription>
												This source work does not have any associated novels
												yet.
											</EmptyDescription>
										</EmptyHeader>
									</Empty>
								)}
							</div>

							<Card size="sm">
								<CardHeader>
									<CardTitle>Overview</CardTitle>
								</CardHeader>
								<CardContent className="space-y-4 text-sm">
									<div className="flex items-center justify-between gap-4">
										<span className="text-muted-foreground">Novels</span>
										<span className="font-medium tabular-nums">
											{novels.length}
										</span>
									</div>
									<div className="flex items-center justify-between gap-4">
										<span className="text-muted-foreground">Type</span>
										<span className="font-medium">Source work</span>
									</div>
									<div className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
										<div className="flex items-center gap-2 font-medium text-foreground">
											<BookOpenIcon className="size-4" />
											Browse novels
										</div>
										<p className="pt-1">
											Use this page as the source-work level view before
											drilling into a specific novel.
										</p>
									</div>
								</CardContent>
							</Card>
						</div>
					</>
				) : null}
			</section>
		</main>
	);
}

export { SourceWorkDetailsPage };
