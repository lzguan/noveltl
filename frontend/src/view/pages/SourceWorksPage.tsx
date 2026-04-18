import { useSearchParams } from "react-router-dom";
import { extractParams } from "@/routes";
import { getSourceWorks } from "@/api/novels";
import { useState, useEffect } from "react";
import { type SourceWorkData } from "@/types/novel";
import { SourceWorkList } from "../components/SourceWorkList";
import { LoadingList } from "../components/LoadingList";
import { StaticRouteInput } from "@/view/components/StaticRouteInput";
import { routeTo } from "@/routes";

function SourceWorksPage() {
    const [searchParams] = useSearchParams();
    const [loading, setLoading] = useState(false);
    const { search } = extractParams.view.sourceworks(searchParams)
    const [sourceWorkData, setSourceWorkData] = useState<SourceWorkData[]>([]);

    useEffect(() => {
        async function loadSourceWorks() {
            setLoading(true);
            const data = await getSourceWorks(search, true);
            setSourceWorkData(data);
            setLoading(false);
        }

        loadSourceWorks();
    }, [search]);
    return (
        <div>
            <section className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-10">
                <header className="flex flex-col gap-3 text-left">
                    <div className="flex flex-col gap-2">
                    <h1 className="text-4xl font-semibold tracking-tight">
                        Browse Works
                    </h1>
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

                <div className="flex flex-col gap-4">
                    {/* SourceWorkCard list */}
                </div>
            </section>
`
            {loading? <LoadingList /> : <SourceWorkList data={sourceWorkData}/>}
        </div>
    )
}

export {
    SourceWorksPage
}