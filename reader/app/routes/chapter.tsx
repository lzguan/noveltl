import { useEffect } from "react";
import { data, Link, useNavigate } from "react-router";
import { SiteHeader } from "../components/SiteHeader";
import { revalidateUnlessSettings } from "../components/SettingsBar";
import {
	getChapterContent,
	getNovel,
	listChapters,
	notFound,
	toRouteError,
} from "../lib/api.server";
import {
	chapterHref,
	chapterLabel,
	isUuid,
	locateChapter,
	parseChapterNum,
	splitParagraphs,
} from "../lib/chapters";
import type { Route } from "./+types/chapter";

export async function loader({ params }: Route.LoaderArgs) {
	const { novelId } = params;
	const chapterNum = parseChapterNum(params.chapterNum);
	if (!isUuid(novelId) || chapterNum === null) notFound();
	try {
		const [novel, chapters] = await Promise.all([getNovel(novelId), listChapters(novelId)]);
		const position = locateChapter(chapters, chapterNum);
		if (!position) notFound();
		const content = await getChapterContent(position.current.chapterId);
		const link = (chapter: typeof position.prev) =>
			chapter
				? { href: chapterHref(novelId, chapter.chapterNum), label: chapterLabel(chapter) }
				: null;
		return data(
			{
				novelTitle: novel.novelTitle,
				contentsHref: `/novel/${novelId}`,
				chapterNum: position.current.chapterNum,
				title: chapterLabel(position.current),
				paragraphs: splitParagraphs(content.chapterContentText),
				prev: link(position.prev),
				next: link(position.next),
			},
			{
				headers: {
					"Cache-Control": "public, max-age=0, s-maxage=60, stale-while-revalidate=600",
					Vary: "Cookie",
				},
			},
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
	if (!loaderData) return [{ title: "Reader" }];
	return [{ title: `${loaderData.title} · ${loaderData.novelTitle}` }];
}

type NavLink = { href: string; label: string } | null;

function ChapterNav({
	prev,
	next,
	contentsHref,
}: {
	prev: NavLink;
	next: NavLink;
	contentsHref: string;
}) {
	const cell =
		"flex-1 rounded border border-line px-3 py-2.5 text-center no-underline hover:bg-hover";
	const disabled =
		"flex-1 rounded border border-line px-3 py-2.5 text-center text-muted opacity-50";
	return (
		<nav className="flex gap-2 text-sm" aria-label="Chapter navigation">
			{prev ? (
				<Link to={prev.href} rel="prev" className={cell} title={prev.label}>
					← Previous
				</Link>
			) : (
				<span className={disabled}>← Previous</span>
			)}
			<Link to={contentsHref} className={cell}>
				Contents
			</Link>
			{next ? (
				<Link
					to={next.href}
					rel="next"
					className={cell}
					title={next.label}
					prefetch="intent"
				>
					Next →
				</Link>
			) : (
				<span className={disabled}>Next →</span>
			)}
		</nav>
	);
}

function useArrowKeyNavigation(prevHref: string | null, nextHref: string | null) {
	const navigate = useNavigate();
	useEffect(() => {
		function onKeyDown(event: KeyboardEvent) {
			if (
				event.defaultPrevented ||
				event.altKey ||
				event.ctrlKey ||
				event.metaKey ||
				event.shiftKey
			) {
				return;
			}
			const target = event.target;
			if (
				target instanceof HTMLElement &&
				(target.isContentEditable ||
					["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
			) {
				return;
			}
			const href =
				event.key === "ArrowLeft" ? prevHref : event.key === "ArrowRight" ? nextHref : null;
			if (href) {
				event.preventDefault();
				navigate(href);
			}
		}
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [navigate, prevHref, nextHref]);
}

export default function ChapterPage({ loaderData }: Route.ComponentProps) {
	const { novelTitle, contentsHref, chapterNum, title, paragraphs, prev, next } = loaderData;
	useArrowKeyNavigation(prev?.href ?? null, next?.href ?? null);

	return (
		<>
			<SiteHeader />
			<main className="mx-auto max-w-2xl px-4 py-5">
				<ChapterNav prev={prev} next={next} contentsHref={contentsHref} />
				<header className="mt-6 mb-6 text-center">
					<Link
						to={contentsHref}
						className="text-sm text-muted no-underline hover:underline"
					>
						{novelTitle}
					</Link>
					<h1 className="mt-1 text-xl font-semibold sm:text-2xl">
						{title === `Chapter ${chapterNum}` ? title : `${chapterNum}. ${title}`}
					</h1>
				</header>
				<article className="chapter-text">
					{paragraphs.length === 0 ? (
						<p className="text-muted">This chapter has no text yet.</p>
					) : (
						paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)
					)}
				</article>
				<div className="mt-10 mb-6">
					<ChapterNav prev={prev} next={next} contentsHref={contentsHref} />
				</div>
			</main>
		</>
	);
}
