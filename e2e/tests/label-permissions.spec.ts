import { expect, test } from "@playwright/test";

import { labelGroupsWithRole, loginByApi, loginToken } from "../helpers/api.js";
import { readSeed } from "../helpers/seed.js";

test("only the label contributor can read the seeded label group by API", async ({ request }) => {
	const seed = readSeed();
	const ownerToken = await loginToken(request, seed.user);
	const otherToken = await loginToken(request, seed.otherUser);

	const ownerGroups = await labelGroupsWithRole(request, ownerToken.access_token, seed.novelId);
	const otherGroups = await labelGroupsWithRole(request, otherToken.access_token, seed.novelId);

	expect(ownerGroups).toEqual(
		expect.arrayContaining([
			expect.objectContaining({
				role: "owner",
				labelGroup: expect.objectContaining({
					labelGroupId: seed.labelGroupId,
					labelGroupName: seed.labelGroupName,
				}),
			}),
		]),
	);
	expect(otherGroups).toEqual([]);
});

test("shows label groups in the editor only for the contributing user", async ({
	browser,
	request,
}) => {
	const seed = readSeed();
	const ownerContext = await browser.newContext();
	const otherContext = await browser.newContext();

	try {
		const ownerPage = await ownerContext.newPage();
		await loginByApi(ownerPage, request, seed.user);
		await ownerPage.goto(`/edit/novels/${seed.novelId}`);
		await ownerPage.getByRole("tab", { name: "Label Groups" }).click();
		await expect(ownerPage.getByText(seed.labelGroupName)).toBeVisible();

		const otherPage = await otherContext.newPage();
		await loginByApi(otherPage, request, seed.otherUser);
		await otherPage.goto(`/edit/novels/${seed.novelId}`);
		await otherPage.getByRole("tab", { name: "Label Groups" }).click();
		await expect(otherPage.getByText("No label groups yet.")).toBeVisible();
		await expect(otherPage.getByText(seed.labelGroupName)).toHaveCount(0);
	} finally {
		await ownerContext.close();
		await otherContext.close();
	}
});
