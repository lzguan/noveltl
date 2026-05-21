import { readNovelsMineNovelsMineGet, readNovelsNovelsGet, type Novel } from "@/client";
import { Button } from "@/components/ui/button";
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyTitle,
} from "@/components/ui/empty";
import { routeTo, extractParams } from "@/routes";
import { LoadingList } from "@/view/components/LoadingList";
import { NovelList } from "@/view/components/NovelList";
import { StaticRouteInput } from "@/view/components/StaticRouteInput";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

function normalizeSearchValue(value: string | undefined) {
    return value?.trim().toLowerCase() ?? "";
}

function matchesNovelSearch(novel: Novel, search: string) {
    if (!search) {
        return true;
    }

    return [novel.novelTitle, novel.novelAuthor, novel.novelDescription]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLowerCase().includes(search));
}

function NovelsPage() {
    const [searchParams] = useSearchParams();
    const { mine, search } = extractParams.view.novels(searchParams);

    const [loading, setLoading] = useState(false);
    const [novels, setNovels] = useState<Novel[]>([]);
    const [, setError] = useState<unknown>(null);

    useEffect(() => {
        let ignore = false;

        async function loadNovels() {
            setLoading(true);
            setError(null);

            const response = mine
                ? await readNovelsMineNovelsMineGet()
                : await readNovelsNovelsGet({
                      query: {
                          titleContains: search,
                      },
                  });

            if (ignore) {
                return;
            }

            if (response.error) {
                setError(response.error);
                setNovels([]);
            } else {
                setNovels(response.data ?? []);
            }

            setLoading(false);
        }

        loadNovels().catch((err) => {
            setError(err);
        });

        return () => {
            ignore = true;
        };
    }, [mine, search]);

    const visibleNovels = useMemo(() => {
        if (!mine) {
            return novels;
        }
        const normalizedSearch = normalizeSearchValue(search);
        return novels.filter((novel) => matchesNovelSearch(novel, normalizedSearch));
    }, [mine, novels, search]);

    return (
        <main>
            <section className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-10">
                <header className="space-y-2">
                    <h1 className="text-4xl font-semibold tracking-tight">Novels</h1>
                    <p className="text-base text-muted-foreground">
                        Browse the novel catalog or narrow the list to novels you can work on directly.
                    </p>
                </header>

                <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
                    <div className="flex flex-wrap gap-2">
                        <Button asChild variant={mine ? "outline" : "default"} size="sm">
                            <Link to={routeTo.view.novels({ search })}>All novels</Link>
                        </Button>
                        <Button asChild variant={mine ? "default" : "outline"} size="sm">
                            <Link to={routeTo.view.novels({ mine: true, search })}>My novels</Link>
                        </Button>
                    </div>
                    <StaticRouteInput
                        toHref={(value: string) => routeTo.view.novels({ mine, search: value })}
                        defaultValue={search}
                    />
                </div>

                {loading ? <LoadingList /> : null}

                {!loading && visibleNovels.length === 0 ? (
                    <Empty className="border">
                        <EmptyHeader>
                            <EmptyTitle>No novels found</EmptyTitle>
                            <EmptyDescription>
                                Try another search term or switch between the full catalog and your editable novels.
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                ) : null}

                {!loading && visibleNovels.length > 0 ? <NovelList novels={visibleNovels} showDescription /> : null}
            </section>
        </main>
    );
}

export { NovelsPage };
