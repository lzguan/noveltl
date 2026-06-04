import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { readNovelsMineNovelsMineGet, type Novel } from "@/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { routeTo } from "@/routes";
import { ArrowRightIcon, BookOpenIcon, LibraryIcon, PencilLineIcon } from "lucide-react";

function formatLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function NovelEditCard({ novel }: { novel: Novel }) {
  return (
    <Link
      to={routeTo.edit.novel(novel.novelId)}
      className="group flex items-start justify-between gap-4 rounded-lg border bg-background p-4 transition-colors hover:bg-muted/50"
    >
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <BookOpenIcon className="size-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate font-medium">{novel.novelTitle}</div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary" className="text-[10px]">
              {formatLabel(novel.novelType)}
            </Badge>
            <Badge variant="outline" className="text-[10px]">
              {novel.languageCode.toUpperCase()}
            </Badge>
          </div>
        </div>
      </div>
      <PencilLineIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </Link>
  );
}

function EditDashboardSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 rounded-lg border p-4">
          <Skeleton className="size-9 shrink-0 rounded-md" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EditDashboardPage() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let ignore = false;

    readNovelsMineNovelsMineGet({ query: { editable: true } })
      .then((res) => {
        if (ignore) return;
        if (res.data) {
          setNovels(res.data);
        } else {
          setError(res.error ?? new Error("Failed to load novels."));
        }
      })
      .catch((err) => {
        if (!ignore) setError(err);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, []);

  return (
    <main>
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-10">
        <header className="space-y-2">
          <h1 className="text-4xl font-semibold tracking-tight">Edit workspace</h1>
          <p className="max-w-3xl text-base text-muted-foreground">
            Select a novel to start editing chapter content and managing labels.
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>Your novels</CardTitle>
            <CardDescription>
              Novels you can edit or manage.
              {!loading && novels.length > 0 ? ` (${novels.length})` : ""}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading && <EditDashboardSkeleton />}

            {!loading && error !== null && (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>Could not load novels</EmptyTitle>
                  <EmptyDescription>
                    Something went wrong while fetching your novels.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}

            {!loading && !error && novels.length === 0 && (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>No novels found</EmptyTitle>
                  <EmptyDescription>
                    You don&apos;t have any novels to edit yet. Browse source works to find novels,
                    or create a new one.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}

            {!loading && !error && novels.length > 0 && (
              <div className="space-y-2">
                {novels.map((novel) => (
                  <NovelEditCard key={novel.novelId} novel={novel} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Button asChild variant="outline" className="w-fit">
          <Link to={routeTo.view.sourceworks()}>
            <LibraryIcon data-icon="inline-start" />
            Browse all source works
            <ArrowRightIcon data-icon="inline-end" />
          </Link>
        </Button>
      </section>
    </main>
  );
}

export { EditDashboardPage };
