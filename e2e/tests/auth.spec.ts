import { expect, test } from "@playwright/test";

import { readSeed } from "../helpers/seed";

test("signs in a seeded non-admin user through the login page", async ({ page }) => {
  const seed = readSeed();

  await page.goto("/login");
  await page.getByLabel("Username").fill(seed.user.username);
  await page.getByLabel("Password").fill(seed.user.password);
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("button", { name: new RegExp(seed.user.username) })).toBeVisible();
});
