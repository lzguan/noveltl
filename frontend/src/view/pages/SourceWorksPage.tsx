import { useSearchParams } from "react-router-dom";
import { extractParams } from "@/routes";
import { useState, useEffect } from "react";
import { SourceWorkList } from "../components/SourceWorkList";
import { LoadingList } from "../components/LoadingList";
import { StaticRouteInput } from "@/view/components/StaticRouteInput";
import { routeTo } from "@/routes";
import { readSourceWorksSourceWorksGet, type SourceWorkDataOutput } from "@/client";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

function SourceWorksPage() {
    const [searchParams] = useSearchParams();
    const [loading, setLoading] = useState(false);
    const { search } = extractParams.view.sourceworks(searchParams)
    const [sourceWorkData, setSourceWorkData] = useState<SourceWorkDataOutput[]>([]);
    const [error, setError] = useState<unknown>(null);

    useEffect(() => {
        let ignore = false;

        async function loadSourceWorks() {
            setLoading(true);
            setError(null);
            const data = await readSourceWorksSourceWorksGet({ query: { titleContains : search } });
            if (ignore) {
                return;
            }
            if (data.data) {
                setSourceWorkData(data.data);
            } else {
                setError(data.error);
                setSourceWorkData([]);
            }
            setLoading(false);
        }

        loadSourceWorks();

        return () => {
            ignore = true;
        };
    }, [search]);

    return (
        <main>
            <section className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-10">
                <header className="flex flex-col gap-3 text-left">
                    <div className="flex flex-col gap-2">
                        <h1 className="text-4xl font-semibold tracking-tight">Browse Works</h1>
                        <p className="text-base text-muted-foreground">
                            Search source works, expand their linked novels inline, or open the dedicated source-work page.
                        </p>
                    </div>
                </header>

                <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
                    <label htmlFor="work-search" className="text-sm font-medium">
                        Search works
                    </label>
                    <StaticRouteInput toHref={(s : string) => routeTo.view.sourceworks({ search: s })} defaultValue={search} />
                    <p className="text-sm text-muted-foreground">
                        Expand a work to see its related novels.
                    </p>
                </div>

                {loading ? <LoadingList /> : null}

                {!loading && error ? (
                    <Empty className="border">
                        <EmptyHeader>
                            <EmptyTitle>Unable to load source works</EmptyTitle>
                            <EmptyDescription>
                                The source-work search could not be loaded for the current query.
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                ) : null}

                {!loading && !error && sourceWorkData.length === 0 ? (
                    <Empty className="border">
                        <EmptyHeader>
                            <EmptyTitle>No source works found</EmptyTitle>
                            <EmptyDescription>
                                Try another title search to find matching source works.
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                ) : null}

                {!loading && !error && sourceWorkData.length > 0 ? <SourceWorkList data={sourceWorkData} /> : null}
            </section>
        </main>
    )
}

export {
    SourceWorksPage
}
