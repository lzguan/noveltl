import { expect, test } from "@playwright/test";

import { latestChapterContent, loginByApi } from "../helpers/api";
import { readSeed } from "../helpers/seed";

test("loads seeded chapter text in the editor", async ({ page, request }) => {
  const seed = readSeed();
  await loginByApi(page, request);

  await page.goto(`/edit/novels/${seed.novelId}`);
  await page.getByText(`Ch.1: ${seed.chapterTitle}`).click();

  await expect(page.locator(".cm-editor")).toBeVisible();
  await expect(page.locator(".cm-content")).toContainText(seed.chapterText);
});

test("persists editor text changes to the backend", async ({ page, request }) => {
  const seed = readSeed();
  const token = await loginByApi(page, request);
  const initialContent = await latestChapterContent(request, token, seed.chapterId);

  await page.goto(`/edit/novels/${seed.novelId}`);
  await page.getByText(`Ch.1: ${seed.chapterTitle}`).click();
  await expect(page.locator(".cm-content")).toContainText(seed.chapterText);

  await page.getByRole("button", { name: "Edit" }).click();
  await page.locator(".cm-content").click();
  await page.keyboard.press(process.platform === "darwin" ? "Meta+Home" : "Control+Home");
  await page.keyboard.type("Dear ");
  const expectedText = `Dear ${initialContent.chapterContentText}`;

  await expect
    .poll(async () => {
      const content = await latestChapterContent(request, token, seed.chapterId);
      return content.chapterContentVersion;
    })
    .toBe(initialContent.chapterContentVersion + 1);

  const updatedContent = await latestChapterContent(request, token, seed.chapterId);
  expect(updatedContent.chapterContentText).toBe(expectedText);

  await page.reload();
  await page.getByText(`Ch.1: ${seed.chapterTitle}`).click();
  await expect(page.locator(".cm-content")).toContainText(expectedText);
});
