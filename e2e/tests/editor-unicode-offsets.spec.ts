import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { apiUrl, latestChapterContent, loginByApi } from "../helpers/api.js";
import { readSeed } from "../helpers/seed.js";

async function createChapter(
	page: Page,
	request: APIRequestContext,
	chapterNum: number,
	text: string,
): Promise<{ token: string; chapterId: string; contentId: string; title: string }> {
	const seed = readSeed();
	const token = await loginByApi(page, request);
	const headers = { Authorization: `Bearer ${token}` };
	const title = `Unicode offsets ${chapterNum}`;
	const created = await request.post(apiUrl(`/novels/${seed.novelId}/chapters`), {
		headers,
		data: { chapterNum, chapterTitle: title, chapterIsPublic: false },
	});
	expect(created.ok(), await created.text()).toBeTruthy();
	const chapter = await created.json();
	if (
		typeof chapter.metadata?.chapterId !== "string" ||
		typeof chapter.content?.chapterContentId !== "string"
	) {
		throw new Error("Chapter creation returned an invalid chapter/content ID.");
	}
	const chapterId: string = chapter.metadata.chapterId;
	const filled = await request.patch(apiUrl(`/chapters/${chapterId}/content`), {
		headers,
		data: {
			chapterContentId: chapter.content.chapterContentId,
			textOps: [{ op: "insert", start: 0, text }],
		},
	});
	expect(filled.ok(), await filled.text()).toBeTruthy();
	const content = await latestChapterContent(request, token, chapterId);
	expect(content.chapterContentText).toBe(text);
	return { token, chapterId, contentId: content.chapterContentId, title };
}

async function openChapter(page: Page, chapterNum: number, title: string, text: string) {
	await page.goto(`/edit/novels/${readSeed().novelId}`);
	await page.getByText(`Ch.${chapterNum}: ${title}`, { exact: true }).click();
	await expect(page.locator(".cm-content")).toHaveText(text);
}

async function placeCaretAfterEmoji(page: Page) {
	await page.getByRole("button", { name: "Edit", exact: true }).click();
	await page.locator(".cm-content").click();
	await page.keyboard.press(process.platform === "darwin" ? "Meta+Home" : "Control+Home");
	await page.keyboard.press("ArrowRight");
	await page.keyboard.press("ArrowRight");
}

test("saves an insertion after an emoji at the position shown in the editor", async ({
	page,
	request,
}) => {
	const fixture = await createChapter(page, request, 9001, "A😀BCDEF");
	await openChapter(page, 9001, fixture.title, "A😀BCDEF");
	await placeCaretAfterEmoji(page);
	const saved = page.waitForResponse(
		(response) =>
			response.request().method() === "PATCH" &&
			new URL(response.url()).pathname.endsWith(`/chapters/${fixture.chapterId}/content`),
	);
	await page.keyboard.insertText("X");
	await expect(page.locator(".cm-content")).toHaveText("A😀XBCDEF");
	expect((await saved).ok()).toBeTruthy();
	const content = await latestChapterContent(request, fixture.token, fixture.chapterId);
	expect(content.chapterContentText).toBe("A😀XBCDEF");
	await page.reload();
	await page.getByText(`Ch.9001: ${fixture.title}`, { exact: true }).click();
	await expect(page.locator(".cm-content")).toHaveText("A😀XBCDEF");
});

test("saves a deletion after an emoji", async ({ page, request }) => {
	const fixture = await createChapter(page, request, 9002, "A😀BCDEF");
	await openChapter(page, 9002, fixture.title, "A😀BCDEF");
	await placeCaretAfterEmoji(page);
	const saved = page.waitForResponse(
		(response) =>
			response.request().method() === "PATCH" &&
			new URL(response.url()).pathname.endsWith(`/chapters/${fixture.chapterId}/content`),
	);
	await page.keyboard.press("Delete");
	await expect(page.locator(".cm-content")).toHaveText("A😀CDEF");
	const response = await saved;
	expect(response.ok(), await response.text()).toBeTruthy();
	expect(
		(await latestChapterContent(request, fixture.token, fixture.chapterId)).chapterContentText,
	).toBe("A😀CDEF");
	await page.reload();
	await page.getByText(`Ch.9002: ${fixture.title}`, { exact: true }).click();
	await expect(page.locator(".cm-content")).toHaveText("A😀CDEF");
});

test("renders a server label after an emoji over its actual word", async ({ page, request }) => {
	const fixture = await createChapter(page, request, 9003, "A😀BCDEF");
	const headers = { Authorization: `Bearer ${fixture.token}` };
	const groupResponse = await request.post(apiUrl("/label-groups"), {
		headers,
		data: { novelId: readSeed().novelId, labelGroupName: "Unicode label offsets" },
	});
	expect(groupResponse.ok(), await groupResponse.text()).toBeTruthy();
	const group = await groupResponse.json();
	const dataResponse = await request.post(
		apiUrl(`/label-groups/${group.labelGroupId}/label-datas`),
		{
			headers,
			data: { chapterContentId: fixture.contentId },
		},
	);
	expect(dataResponse.ok(), await dataResponse.text()).toBeTruthy();
	const data = await dataResponse.json();
	const labelResponse = await request.patch(apiUrl(`/label-datas/${data.labelDataId}`), {
		headers,
		data: { ops: [{ op: "add", startPos: 2, endPos: 4, entityGroup: "DEMO" }] },
	});
	expect(labelResponse.ok(), await labelResponse.text()).toBeTruthy();
	await openChapter(page, 9003, fixture.title, "A😀BCDEF");
	const label = page.locator('.cm-content span[style*="border-bottom"]');
	await expect(label).toHaveCount(1);
	await expect(label).toHaveText("BC");
});

test("highlights the searched term after emoji in its preview", async ({ page, request }) => {
	const fixture = await createChapter(page, request, 9004, "😀😀白玫走进花园。");
	await openChapter(page, 9004, fixture.title, "😀😀白玫走进花园。");
	await page.getByRole("tab", { name: "Search", exact: true }).click();
	await page.getByRole("textbox", { name: "Search text" }).fill("白玫");
	await page.getByRole("button", { name: "Search", exact: true }).click();
	await page.getByRole("button", { name: `Expand Chapter 9004 · ${fixture.title}` }).click();
	const match = page.locator("mark");
	await expect(match).toHaveCount(1);
	await expect(match).toHaveText("白玫");
});

for (const cached of [false, true]) {
	test(`search navigation selects a rare CJK term in a ${cached ? "cached" : "newly loaded"} chapter`, async ({
		page,
		request,
	}) => {
		const number = cached ? 9006 : 9005;
		const fixture = await createChapter(page, request, number, "😀😀𠮷走进花园。");
		if (cached) await openChapter(page, number, fixture.title, "😀😀𠮷走进花园。");
		else await page.goto(`/edit/novels/${readSeed().novelId}`);
		await page.getByRole("tab", { name: "Search", exact: true }).click();
		await page.getByRole("textbox", { name: "Search text" }).fill("𠮷");
		await page.getByRole("button", { name: "Search", exact: true }).click();
		await page
			.getByRole("button", { name: `Expand Chapter ${number} · ${fixture.title}` })
			.click();
		const occurrence = page.getByRole("button", { name: "😀😀𠮷走进花园。", exact: true });
		await occurrence.click();
		await expect(page.locator(".cm-content")).toHaveText("😀😀𠮷走进花园。");
		await page.getByRole("button", { name: "Edit", exact: true }).click();
		await page.locator(".cm-content").focus();
		await page.keyboard.insertText("X");
		await expect(page.locator(".cm-content")).toHaveText("😀😀X走进花园。");
		await expect
			.poll(
				async () =>
					(await latestChapterContent(request, fixture.token, fixture.chapterId))
						.chapterContentText,
			)
			.toBe("😀😀X走进花园。");
	});
}
