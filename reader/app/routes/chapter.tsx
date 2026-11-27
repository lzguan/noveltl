import { type MouseEvent, useEffect, useState } from "react";
import { data, Link, redirect, type ShouldRevalidateFunctionArgs, useNavigate } from "react-router";
import {
	AnchoredFeedbackSheet,
	ChapterFeedbackWidget,
	type FeedbackActionData,
} from "../components/ChapterFeedback";
import { revalidateUnlessSettings } from "../components/SettingsBar";
import { SiteHeader } from "../components/SiteHeader";
import { getChapter, notFound, toRouteError } from "../lib/api.server";
import {
	chapterHref,
	chapterLabel,
	isUuid,
	parseChapterNum,
	splitParagraphs,
} from "../lib/chapters";
import {
	FeedbackApiError,
	parseFeedbackFormData,
	submitChapterFeedback,
} from "../lib/feedback.server";
import {
	extractWordAnchor,
	type FeedbackAnchor,
	resolveCaretOffsetInElement,
	resolvePointToCaret,
} from "../lib/feedbackAnchor";
import type { Route } from "./+types/chapter";

export async function loader({ params, request }: Route.LoaderArgs) {
	const { novelId } = params;
	const chapterNum = parseChapterNum(params.chapterNum);
	if (!isUuid(novelId) || chapterNum === null) notFound();

	const url = new URL(request.url);
	const rawFeedback = url.searchParams.get("feedback");
	const feedbackStatus: "thanks" | "error" | null =
		rawFeedback === "thanks" ? "thanks" : rawFeedback === "error" ? "error" : null;

	try {
		const chapter = await getChapter(novelId, chapterNum);
		const link = (nav: typeof chapter.prev) =>
			nav ? { href: chapterHref(novelId, nav.chapterNum), label: chapterLabel(nav) } : null;
		const headers: Record<string, string> =
			feedbackStatus !== null
				? { "Cache-Control": "no-store" }
				: {
						"Cache-Control":
							"public, max-age=0, s-maxage=300, stale-while-revalidate=3600",
						Vary: "Cookie",
					};
		return data(
			{
				novelId,
				novelTitle: chapter.novelTitle,
				contentsHref: `/novel/${novelId}`,
				chapterNum: chapter.chapterNum,
				contentHash: chapter.contentHash,
				title: chapterLabel(chapter),
				paragraphs: splitParagraphs(chapter.body),
				prev: link(chapter.prev),
				next: link(chapter.next),
				feedbackStatus,
			},
			{ headers },
		);
	} catch (error) {
		toRouteError(error);
	}
}

export async function action({ params, request }: Route.ActionArgs) {
	const { novelId } = params;
	const chapterNum = parseChapterNum(params.chapterNum);
	if (!isUuid(novelId) || chapterNum === null) notFound();

	const formData = await request.formData();
	const isJs = formData.get("js") === "1";
	const parsed = parseFeedbackFormData(formData);
	const noStore = { "Cache-Control": "no-store" };

	if (!parsed.ok) {
		if (isJs) {
			const payload: FeedbackActionData = { ok: false, error: parsed.error };
			return data(payload, { status: 400, headers: noStore });
		}
		return redirect(`${chapterHref(novelId, chapterNum)}?feedback=error#chapter-feedback`, {
			headers: noStore,
		});
	}

	try {
		const created = await submitChapterFeedback(novelId, chapterNum, parsed.submission, {
			forwardedFor: request.headers.get("x-forwarded-for"),
			userAgent: request.headers.get("user-agent"),
		});
		if (isJs) {
			const payload: FeedbackActionData = {
				ok: true,
				kind: parsed.submission.kind,
				emoji: parsed.submission.kind === "reaction" ? parsed.submission.emoji : undefined,
				feedbackId: created.feedbackId,
			};
			return data(payload, { headers: noStore });
		}
		return redirect(`${chapterHref(novelId, chapterNum)}?feedback=thanks#chapter-feedback`, {
			headers: noStore,
		});
	} catch (error) {
		const message =
			error instanceof FeedbackApiError
				? error.detail
				: "Could not submit feedback right now.";
		const status = error instanceof FeedbackApiError ? error.status : 502;
		if (isJs) {
			const payload: FeedbackActionData = { ok: false, error: message };
			return data(payload, { status, headers: noStore });
		}
		return redirect(`${chapterHref(novelId, chapterNum)}?feedback=error#chapter-feedback`, {
			headers: noStore,
		});
	}
}

export function headers({ loaderHeaders }: Route.HeadersArgs) {
	return loaderHeaders;
}

export function shouldRevalidate(args: ShouldRevalidateFunctionArgs): boolean {
	if (args.formMethod?.toUpperCase() === "POST" && args.formData?.get("js") === "1") {
		return false;
	}
	return revalidateUnlessSettings(args);
}

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

function useArrowKeyNavigation(
	prevHref: string | null,
	nextHref: string | null,
	disabled: boolean,
) {
	const navigate = useNavigate();
	useEffect(() => {
		if (disabled) return;
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
	}, [navigate, prevHref, nextHref, disabled]);
}

export default function ChapterPage({ loaderData }: Route.ComponentProps) {
	const {
		novelId,
		novelTitle,
		contentsHref,
		chapterNum,
		contentHash,
		title,
		paragraphs,
		prev,
		next,
		feedbackStatus,
	} = loaderData;
	const chapterKey = `${novelId}:${chapterNum}`;
	const [feedbackMode, setFeedbackMode] = useState(false);
	const [selectedAnchor, setSelectedAnchor] = useState<{
		chapterKey: string;
		anchor: FeedbackAnchor;
	} | null>(null);

	const activeAnchor =
		selectedAnchor && selectedAnchor.chapterKey === chapterKey ? selectedAnchor.anchor : null;

	useArrowKeyNavigation(prev?.href ?? null, next?.href ?? null, activeAnchor !== null);

	function toggleFeedbackMode() {
		setFeedbackMode((current) => {
			if (current) {
				setSelectedAnchor(null);
			}
			return !current;
		});
	}

	function handleArticleClick(event: MouseEvent<HTMLElement>) {
		if (!feedbackMode) return;
		const target = event.target;
		if (!(target instanceof Element)) return;
		const paragraphEl = target.closest("p[data-paragraph-index]");
		if (!paragraphEl) return;

		const rawIndex = paragraphEl.getAttribute("data-paragraph-index");
		if (rawIndex === null) return;
		const paragraphIndex = Number(rawIndex);
		if (!Number.isInteger(paragraphIndex) || paragraphIndex < 0) return;

		const paragraphText = paragraphs[paragraphIndex];
		if (!paragraphText) return;

		const caret = resolvePointToCaret(event.clientX, event.clientY);
		const offset = caret
			? resolveCaretOffsetInElement(paragraphEl, caret.node, caret.offset)
			: null;
		const anchor = extractWordAnchor(paragraphText, paragraphIndex, offset ?? 0);
		if (anchor) {
			setSelectedAnchor({ chapterKey, anchor });
		}
	}

	const feedbackModeToggle = (
		<button
			type="button"
			aria-pressed={feedbackMode}
			onClick={toggleFeedbackMode}
			className={`rounded border px-2.5 py-1 text-xs font-medium transition ${
				feedbackMode
					? "border-ink bg-ink text-page"
					: "border-line text-muted hover:bg-hover hover:text-ink"
			}`}
		>
			{feedbackMode ? "Feedback mode: On" : "Feedback mode"}
		</button>
	);

	return (
		<>
			<SiteHeader extra={feedbackModeToggle} />
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

				{feedbackMode ? (
					<div
						role="status"
						className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-line bg-hover px-3.5 py-2 text-xs text-ink"
					>
						<span>Feedback mode active — tap any word to flag an issue.</span>
						<button
							type="button"
							onClick={toggleFeedbackMode}
							className="shrink-0 rounded border border-line bg-page px-2 py-0.5 font-medium text-ink hover:bg-hover"
						>
							Done
						</button>
					</div>
				) : null}

				<article
					className={
						feedbackMode ? "chapter-text chapter-text--feedback-mode" : "chapter-text"
					}
					onClick={feedbackMode ? handleArticleClick : undefined}
				>
					{paragraphs.length === 0 ? (
						<p className="text-muted">This chapter has no text yet.</p>
					) : (
						paragraphs.map((paragraph, index) => (
							<p key={index} data-paragraph-index={index}>
								{paragraph}
							</p>
						))
					)}
				</article>

				<ChapterFeedbackWidget
					key={chapterKey}
					contentHash={contentHash}
					feedbackStatus={feedbackStatus}
				/>

				<div className="mt-8 mb-6">
					<ChapterNav prev={prev} next={next} contentsHref={contentsHref} />
				</div>
			</main>

			{activeAnchor ? (
				<AnchoredFeedbackSheet
					key={`${chapterKey}:${activeAnchor.paragraphIndex}:${activeAnchor.startOffset}:${activeAnchor.endOffset}`}
					anchor={activeAnchor}
					contentHash={contentHash}
					onClose={() => setSelectedAnchor(null)}
				/>
			) : null}
		</>
	);
}
