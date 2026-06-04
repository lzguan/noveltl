import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { routeTo } from "@/routes";
import { BookOpenIcon, LibraryIcon, PencilLineIcon } from "lucide-react";

function DashboardPage() {
  return (
    <main>
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-10">
        <header className="space-y-2">
          <h1 className="text-4xl font-semibold tracking-tight">NovelTL</h1>
          <p className="max-w-3xl text-base text-muted-foreground">
            Browse source works and novels on the view side, or jump into the editing workspace when
            you are ready to work on chapter data.
          </p>
        </header>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex size-11 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <LibraryIcon />
              </div>
              <CardTitle className="pt-3 text-2xl">Browse</CardTitle>
              <CardDescription>
                Explore source works, novels, and their chapters. Search and filter by title.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button asChild>
                <Link to={routeTo.view.sourceworks()}>
                  <LibraryIcon data-icon="inline-start" />
                  Source Works
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link to={routeTo.view.novels()}>
                  <BookOpenIcon data-icon="inline-start" />
                  Novels
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex size-11 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <PencilLineIcon />
              </div>
              <CardTitle className="pt-3 text-2xl">Edit</CardTitle>
              <CardDescription>
                Work on chapter text, manage labels, and run automated tooling on your novels.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button asChild>
                <Link to={routeTo.edit.dashboard()}>
                  <PencilLineIcon data-icon="inline-start" />
                  Edit Home
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>
    </main>
  );
}

export { DashboardPage };
