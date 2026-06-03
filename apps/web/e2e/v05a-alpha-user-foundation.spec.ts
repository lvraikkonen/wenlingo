import { expect, test } from "@playwright/test";

test("new alpha family can join with email code and keep learning flow", async ({
  page,
}) => {
  await page.goto("/alpha/start");
  await expect(page.getByText("小文星球 WenLingo")).toBeVisible();
  await page.getByLabel("邮箱").fill("parent@example.com");
  await page.getByLabel("内测邀请码").fill("ALPHA-E2E");
  await page.getByRole("button", { name: "获取验证码" }).click();
  await page.getByLabel("6 位验证码").fill("123456");
  await page.getByRole("button", { name: "继续使用 Alpha" }).click();
  await expect(page).toHaveURL(/\/parent\/children/);
});

test("legacy parent id can migrate to email account", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "wenlingo_alpha_parent_id",
      "legacy-e2e-parent",
    );
  });
  await page.goto("/alpha/start");
  await expect(
    page.getByText("绑定邮箱继续使用当前 Alpha 家庭"),
  ).toBeVisible();
});
