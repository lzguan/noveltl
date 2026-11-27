import { data, Link } from "react-router";
import { SiteHeader } from "../components/SiteHeader";
import { revalidateUnlessSettings } from "../components/SettingsBar";
import { getNovel, listChapters, notFound, toRouteError } from "../lib/api.server";
import { chapterHref, chapterLabel, isUuid, sortChapters } from "../lib/chapters";
import type { Route } from "./+types/novel";

export async function loader({ params }: Route.LoaderArgs) {
	const { novelId } = params;
	if (!isUuid(novelId)) notFound();
	try {
		const [novel, chapters] = await Promise.all([getNovel(novelId), listChapters(novelId)]);
		return data(
			{
				novel: {
					novelId: novel.novelId,
					novelTitle: novel.title,
					novelAuthor: novel.author ?? null,
					novelDescription: novel.description ?? null,
				},
				chapters: sortChapters(chapters).map((chapter) => ({
					chapterNum: chapter.chapterNum,
					label: chapterLabel(chapter),
				})),
			},
			{ headers: { "Cache-Control": "public, max-age=0, s-maxage=60", Vary: "Cookie" } },
		);
	} catch (error) {
		toRouteError(error);
	}
}

export function headers({ loaderHeaders }: Route.HeadersArgs) {
	return loaderHeaders;
}

export const shouldRevalidate = revalidateUnlessSettings;

export function meta({ loaderData }: Route.MetaArgs) {
	return [{ title: loaderData ? `${loaderData.novel.novelTitle} · Reader` : "Reader" }];
}

export default function NovelPage({ loaderData }: Route.ComponentProps) {
	const { novel, chapters } = loaderData;
	const first = chapters[0];
	return (
		<>
			<SiteHeader />
			<main className="mx-auto max-w-3xl px-4 py-6">
				<h1 className="text-2xl font-semibold">{novel.novelTitle}</h1>
				{novel.novelAuthor ? <p className="mt-1 text-muted">{novel.novelAuthor}</p> : null}
				{novel.novelDescription ? (
					<p className="mt-4 whitespace-pre-line">{novel.novelDescription}</p>
				) : null}
				{first ? (
					<p className="mt-4">
						<Link
							to={chapterHref(novel.novelId, first.chapterNum)}
							className="font-medium"
						>
							Start reading →
						</Link>
					</p>
				) : null}

				<h2 className="mt-8 mb-2 text-lg font-semibold">
					Contents{" "}
					<span className="text-sm font-normal text-muted">({chapters.length})</span>
				</h2>
				{chapters.length === 0 ? (
					<p className="text-muted">No chapters are available yet.</p>
				) : (
					<ol className="grid border-t border-line sm:grid-cols-2 sm:gap-x-6">
						{chapters.map((chapter) => (
							<li key={chapter.chapterNum} className="border-b border-line">
								<Link
									to={chapterHref(novel.novelId, chapter.chapterNum)}
									className="block truncate py-2 no-underline hover:underline"
								>
									<span className="mr-2 text-sm text-muted tabular-nums">
										{chapter.chapterNum}.
									</span>
									{chapter.label}
								</Link>
							</li>
						))}
					</ol>
				)}
			</main>
		</>
	);
}
