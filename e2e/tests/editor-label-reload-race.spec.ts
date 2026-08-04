import { expect, test } from "@playwright/test";

import { latestChapterContent, loginByApi } from "../helpers/api.js";
import { readSeed } from "../helpers/seed.js";

const reloadQueueDelayMs = 2_000;

async function startPendingLabelReloadTextRace({
	page,
	request,
	prefix,
	groupName,
}: {
	page: Parameters<typeof loginByApi>[0];
	request: Parameters<typeof loginByApi>[1];
	prefix: string;
	groupName: string;
}) {
	const seed = readSeed();
	const token = await loginByApi(page, request);
	const initialContent = await latestChapterContent(request, token, seed.chapterId);
	const reloadPath = `/api/edit-chapter-data/${seed.chapterId}/label-data`;

	let releaseReload = () => {};
	const reloadGate = new Promise<void>((resolve) => {
		releaseReload = resolve;
	});
	let reportReloadStarted = () => {};
	const reloadStarted = new Promise<void>((resolve) => {
		reportReloadStarted = resolve;
	});
	let reloadIntercepted = false;

	await page.route(`**${reloadPath}`, async (route) => {
		if (!reloadIntercepted && route.request().method() === "POST") {
			reloadIntercepted = true;
			reportReloadStarted();
			await reloadGate;
		}
		await route.continue();
	});

	await page.goto(`/edit/novels/${seed.novelId}`);
	await page.getByText(`Ch.1: ${seed.chapterTitle}`).click();
	await expect(page.locator(".cm-content")).toContainText(initialContent.chapterContentText);

	await page.getByRole("button", { name: "Edit" }).click();
	await page.getByRole("tab", { name: "Label Groups" }).click();
	const labelGroupPanel = page.getByRole("tabpanel", { name: "Label Groups" });
	await labelGroupPanel.locator("button:has(svg.lucide-plus)").click();
	await labelGroupPanel.getByPlaceholder("Label group name").fill(groupName);
	await labelGroupPanel.getByRole("button", { name: "Add" }).click();
	await reloadStarted;

	const editor = page.locator(".cm-content");
	await editor.click();
	await page.keyboard.press(process.platform === "darwin" ? "Meta+Home" : "Control+Home");
	await page.keyboard.type(prefix);
	await expect(editor).toContainText(`${prefix}${initialContent.chapterContentText}`);

	// Give the controller's debounce and flush loops time to enqueue the text request
	// while the new group's first label-data reload is still in flight.
	await page.waitForTimeout(reloadQueueDelayMs);

	const reloadFinished = page.waitForResponse(
		(response) =>
			response.request().method() === "POST" &&
			new URL(response.url()).pathname === reloadPath,
	);
	releaseReload();
	await reloadFinished;
	await page.unroute(`**${reloadPath}`);

	return {
		editor,
		expectedText: `${prefix}${initialContent.chapterContentText}`,
		seed,
		token,
	};
}

test("persists text queued during a new label group's initial reload", async ({
	page,
	request,
}, testInfo) => {
	const race = await startPendingLabelReloadTextRace({
		page,
		request,
		prefix: "Queued during reload: ",
		groupName: `Reload race persistence ${testInfo.workerIndex}`,
	});

	await expect
		.poll(async () => {
			const content = await latestChapterContent(request, race.token, race.seed.chapterId);
			return content.chapterContentText;
		})
		.toBe(race.expectedText);
});

test("continues processing text after a new label reload overlaps an edit", async ({
	page,
	request,
}, testInfo) => {
	const firstPrefix = "First queued edit: ";
	const race = await startPendingLabelReloadTextRace({
		page,
		request,
		prefix: firstPrefix,
		groupName: `Reload race recovery ${testInfo.workerIndex}`,
	});

	const secondPrefix = "Follow-up edit: ";
	await race.editor.click();
	await page.keyboard.press(process.platform === "darwin" ? "Meta+Home" : "Control+Home");
	await page.keyboard.type(secondPrefix);
	const expectedText = `${secondPrefix}${race.expectedText}`;
	await expect(race.editor).toContainText(expectedText);

	await expect
		.poll(async () => {
			const content = await latestChapterContent(request, race.token, race.seed.chapterId);
			return content.chapterContentText;
		})
		.toBe(expectedText);
});
