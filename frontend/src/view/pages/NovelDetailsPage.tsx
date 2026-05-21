import {
    readChaptersByNovelChaptersGet,
    readNovelNovelsNovelIdGet,
    type Chapter,
    type Novel,
} from "@/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardAction,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyTitle,
} from "@/components/ui/empty";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { logger } from "@/lib/logging";
import { routeTo, extractParams } from "@/routes";
import { BookOpenIcon, ChevronLeftIcon, FileTextIcon, PencilIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

function formatLabel(value: string) {
    return value
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function formatVisibility(value: Novel["novelVisibility"]) {
    switch (value) {
        case 0:
            return "Private";
        case 1:
            return "Restricted";
        case 2:
            return "Unlisted";
        case 3:
            return "Public";
    }
}

function NovelDetailsSkeleton() {
    return (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <Card>
                <CardHeader>
                    <Skeleton className="h-8 w-2/3" />
                    <Skeleton className="h-4 w-1/3" />
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                </CardContent>
            </Card>
            <Card>
                <CardHeader>
                    <Skeleton className="h-5 w-24" />
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-4/5" />
                    <Skeleton className="h-4 w-2/3" />
                </CardContent>
            </Card>
        </div>
    );
}

function NovelMetadata({ novel, chapterCount }: { novel: Novel; chapterCount: number }) {
    return (
        <Card size="sm">
            <CardHeader>
                <CardTitle>Details</CardTitle>
                <CardDescription>Source and availability</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
                <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary">{formatLabel(novel.novelType)}</Badge>
                    <Badge variant="outline">{formatVisibility(novel.novelVisibility)}</Badge>
                    <Badge variant="outline">{novel.languageCode.toUpperCase()}</Badge>
                </div>
                <Separator />
                <dl className="grid gap-3 text-sm">
                    <div className="flex items-center justify-between gap-4">
                        <dt className="text-muted-foreground">Chapters</dt>
                        <dd className="font-medium tabular-nums">{chapterCount}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                        <dt className="text-muted-foreground">Author</dt>
                        <dd className="max-w-36 truncate text-right font-medium">
                            {novel.novelAuthor || "Unknown"}
                        </dd>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                        <dt className="text-muted-foreground">Source work</dt>
                        <dd className="max-w-36 truncate text-right font-medium">
                            <Link className="hover:underline" to={routeTo.view.sourcework(novel.sourceWorkId)}>
                                View source
                            </Link>
                        </dd>
                    </div>
                </dl>
            </CardContent>
        </Card>
    );
}

function ChapterList({ chapters }: { chapters: Chapter[] }) {
    if (chapters.length === 0) {
        return (
            <Empty className="border">
                <EmptyHeader>
                    <EmptyTitle>No chapters found</EmptyTitle>
                    <EmptyDescription>
                        There are no chapters in this range for the selected novel.
                    </EmptyDescription>
                </EmptyHeader>
            </Empty>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Chapters</CardTitle>
                <CardDescription>{chapters.length} chapters in the current range</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
                {chapters.map((chapter) => (
                    <Link
                        key={chapter.chapterId}
                        to={routeTo.view.chapter(chapter.chapterId)}
                        className="group flex items-center justify-between gap-4 rounded-md border bg-background p-3 text-sm transition-colors hover:bg-muted"
                    >
                        <div className="flex min-w-0 items-center gap-3">
                            <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                                <FileTextIcon />
                            </div>
                            <div className="min-w-0">
                                <div className="truncate font-medium">
                                    {chapter.chapterTitle || `Chapter ${chapter.chapterNum}`}
                                </div>
                                <div className="text-muted-foreground">
                                    Chapter {chapter.chapterNum}
                                </div>
                            </div>
                        </div>
                        <Badge variant={chapter.chapterIsPublic ? "secondary" : "outline"}>
                            {chapter.chapterIsPublic ? "Public" : "Private"}
                        </Badge>
                    </Link>
                ))}
            </CardContent>
        </Card>
    );
}

function NovelDetailsPage() {
    const params = useParams();
    const [searchParams] = useSearchParams();

    const [novel, setNovel] = useState<Novel | null>(null);
    const [chapters, setChapters] = useState<Chapter[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<unknown>(null);

    useEffect(() => {
        let ignore = false;

        async function loadData() {
            const novelId = params.novelId;
            if (!novelId) {
                setError(new Error("Missing novel id."));
                setNovel(null);
                setChapters([]);
                return;
            }

            setLoading(true);
            setError(null);

            const data = await readNovelNovelsNovelIdGet({
                path: {
                    novelId,
                },
            });

            if (ignore) return;

            if (data.error) {
                setError(data.error);
                setNovel(null);
                setChapters([]);
                setLoading(false);
                return;
            }

            setNovel(data.data);

            const { start, end } = extractParams.view.novel(searchParams);
            const chapterData = await readChaptersByNovelChaptersGet({
                query: {
                    novelId,
                    start: start ?? null,
                    end: end ?? null,
                },
            });

            if (ignore) return;

            if (chapterData.error) {
                setError(chapterData.error);
                setChapters([]);
            } else {
                setChapters(chapterData.data);
            }

            setLoading(false);
        }

        loadData().catch((err) => {
            logger.error("Failed to load novel details", err);
        });

        return () => {
            ignore = true;
        };
    }, [params.novelId, searchParams]);

    return (
        <main>
            <section className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-10">
                <Button asChild variant="ghost" className="w-fit pl-2">
                    <Link to={routeTo.view.novels()}>
                        <ChevronLeftIcon data-icon="inline-start" />
                        Novels
                    </Link>
                </Button>

                {loading && <NovelDetailsSkeleton />}

                {!loading && Boolean(error) && (
                    <Empty className="border">
                        <EmptyHeader>
                            <EmptyTitle>Unable to load novel</EmptyTitle>
                            <EmptyDescription>
                                The novel details or chapter list could not be loaded.
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                )}

                {!loading && !error && novel && (
                    <>
                        <Card>
                            <CardHeader>
                                <div className="flex min-w-0 items-start gap-4">
                                    <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                                        <BookOpenIcon />
                                    </div>
                                    <div className="min-w-0">
                                        <CardTitle className="text-3xl tracking-tight">
                                            {novel.novelTitle}
                                        </CardTitle>
                                        <CardDescription>
                                            {novel.novelAuthor || "Unknown author"}
                                        </CardDescription>
                                    </div>
                                </div>
                                <CardAction>
                                    <Button asChild variant="outline" size="sm">
                                        <Link to={routeTo.edit.novel(novel.novelId)}>
                                            <PencilIcon data-icon="inline-start" />
                                            Edit
                                        </Link>
                                    </Button>
                                </CardAction>
                            </CardHeader>
                        </Card>

                        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
                            <div className="flex min-w-0 flex-col gap-6">
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Description</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <p className="text-sm leading-7 text-muted-foreground">
                                            {novel.novelDescription || "No description available."}
                                        </p>
                                    </CardContent>
                                </Card>

                                <ChapterList chapters={chapters} />
                            </div>

                            <NovelMetadata novel={novel} chapterCount={chapters.length} />
                        </div>
                    </>
                )}
            </section>
        </main>
    );
}

export { NovelDetailsPage };
