import { expect, test } from "@playwright/test";

import { loginByApi } from "../helpers/api.js";
import { readSeed } from "../helpers/seed.js";

test("navigates between seeded chapters in the editor", async ({ page, request }) => {
	const seed = readSeed();
	await loginByApi(page, request);

	await page.goto(`/edit/novels/${seed.novelId}`);

	await page.getByText(`Ch.1: ${seed.chapterTitle}`).click();
	await expect(page.locator(".cm-content")).toContainText(seed.chapterText);

	await page.getByText(`Ch.2: ${seed.secondChapterTitle}`).click();
	await expect(page.locator(".cm-content")).toContainText(seed.secondChapterText);
});
