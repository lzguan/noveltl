import { data, Link } from "react-router";
import { SiteHeader } from "../components/SiteHeader";
import { revalidateUnlessSettings } from "../components/SettingsBar";
import { listNovels, toRouteError } from "../lib/api.server";
import type { Route } from "./+types/home";

export async function loader() {
	try {
		const novels = await listNovels();
		return data(
			{
				novels: novels
					.map((novel) => ({
						novelId: novel.novelId,
						novelTitle: novel.title,
						novelAuthor: novel.author ?? null,
						novelDescription: novel.description ?? null,
					}))
					.sort((a, b) => a.novelTitle.localeCompare(b.novelTitle)),
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

export function meta() {
	return [{ title: "Library · Reader" }];
}

export default function Home({ loaderData }: Route.ComponentProps) {
	const { novels } = loaderData;
	return (
		<>
			<SiteHeader />
			<main className="mx-auto max-w-3xl px-4 py-6">
				<h1 className="mb-4 text-xl font-semibold">Library</h1>
				{novels.length === 0 ? (
					<p className="text-muted">No novels are available to read yet.</p>
				) : (
					<ul className="divide-y divide-line border-y border-line">
						{novels.map((novel) => (
							<li key={novel.novelId} className="py-3">
								<Link
									to={`/novel/${novel.novelId}`}
									className="text-lg font-medium"
								>
									{novel.novelTitle}
								</Link>
								{novel.novelAuthor ? (
									<span className="ml-2 text-sm text-muted">
										{novel.novelAuthor}
									</span>
								) : null}
								{novel.novelDescription ? (
									<p className="mt-1 line-clamp-2 text-sm text-muted">
										{novel.novelDescription}
									</p>
								) : null}
							</li>
						))}
					</ul>
				)}
			</main>
		</>
	);
}
