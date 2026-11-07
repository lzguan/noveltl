import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import { Prov } from "../../controller/types/helperTypes";
import { CProvId, type ProvChapter } from "../../controller/types/idTypes";
import { TermSearchPanel } from "./TermSearchPanel";

const CHAPTERS: ProvChapter[] = [3, 7].map((chapterNum) =>
	Prov({
		chapterId: CProvId(`00000000-0000-0000-0000-00000000000${chapterNum}`),
		chapterNum,
		chapterTitle: `Title ${chapterNum}`,
		chapterIsPublic: false,
		novelId: "novel-1",
	}),
);

function chapter(num: number, matchCount: number) {
	return {
		chapterId: `chapter-${num}`,
		chapterNum: num,
		chapterContentId: `content-${num}`,
		matchCount,
	};
}

// Real client and UI; only HTTP is simulated.
function setup() {
	const reads: string[] = [];
	vi.stubGlobal(
		"fetch",
		vi.fn(async (url: string) => {
			reads.push(url);
			const parsed = new URL(url, "http://localhost");
			if (parsed.pathname.startsWith("/api/chapter-contents/content-3/")) {
				return Response.json({
					chapterContentId: "content-3",
					occurrences: [
						{ start: 12, preview: "他看见白玫走来", previewStart: 9 },
						{ start: 40, preview: "白玫笑了", previewStart: 40 },
						{ start: 80, preview: "一二三四五六七八九十白玫", previewStart: 70 },
					],
				});
			}
			if (parsed.searchParams.get("offset") === "1") {
				return Response.json({
					totalChapters: 2,
					totalMatches: 3,
					nextOffset: null,
					chapters: [chapter(7, 1)],
				});
			}
			if (parsed.searchParams.get("term") === "缺失") {
				return Response.json({ detail: "Novel not found." }, { status: 404 });
			}
			return Response.json({
				totalChapters: 2,
				totalMatches: 3,
				nextOffset: 1,
				chapters: [chapter(3, 2)],
			});
		}),
	);
	const gotoText = vi.fn();
	render(<TermSearchPanel novelId="novel-1" chapters={CHAPTERS} gotoText={gotoText} />);
	const search = (term: string) => {
		fireEvent.change(screen.getByRole("textbox", { name: "Search text" }), {
			target: { value: term },
		});
		fireEvent.click(screen.getByRole("button", { name: "Search" }));
	};
	return { reads, gotoText, search };
}

afterEach(() => {
	vi.unstubAllGlobals();
});

it("lists matching chapters by number and title and pages in more chapters", async () => {
	const { reads, search } = setup();
	fireEvent.change(screen.getByRole("textbox", { name: "From chapter" }), {
		target: { value: "2" },
	});
	search("白玫");

	expect(await screen.findByText("3 results in 2 chapters")).toBeVisible();
	expect(screen.getByRole("button", { name: "Expand Chapter 3 · Title 3" })).toBeVisible();
	expect(reads[0]).toContain("term=%E7%99%BD%E7%8E%AB");
	expect(reads[0]).toContain("startChapterNum=2");
	expect(reads.some((url) => url.includes("/chapter-contents/"))).toBe(false);

	fireEvent.click(screen.getByRole("button", { name: "Load more chapters" }));
	expect(await screen.findByRole("button", { name: "Expand Chapter 7 · Title 7" })).toBeVisible();
	expect(screen.queryByRole("button", { name: "Load more chapters" })).not.toBeInTheDocument();
});

it("loads previews when a chapter opens and jumps to the pinned content version", async () => {
	const { reads, gotoText, search } = setup();
	search("白玫");
	fireEvent.click(await screen.findByRole("button", { name: "Expand Chapter 3 · Title 3" }));

	const first = await screen.findByRole("button", { name: "他看见白玫走来" });
	expect(within(first).getByText("白玫").tagName).toBe("MARK");
	expect(reads.filter((url) => url.includes("/chapter-contents/content-3/"))).toHaveLength(1);

	// A long lead-in is shortened so the match stays visible; the full line is the tooltip.
	const long = screen.getByRole("button", { name: "…三四五六七八九十白玫" });
	expect(long).toHaveAttribute("title", "一二三四五六七八九十白玫");

	fireEvent.click(first);
	expect(gotoText).toHaveBeenCalledWith("chapter-3", {
		start: 12,
		end: 14,
		ccServId: "content-3",
	});
});

it("reports a failed search", async () => {
	const { search } = setup();
	search("缺失");
	await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Novel not found."));
});
