import { expect, test } from "@playwright/test";

test.use({
  baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000",
});

test("family demo completes the MVP learning loop", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "小文星球" })).toBeVisible();
  await page.getByRole("button", { name: "进入家庭内测" }).click();

  await expect(page.getByRole("link", { name: "小宇" })).toBeVisible();
  await expect(page.getByRole("link", { name: "小晴" })).toBeVisible();
  await expect(page.getByRole("link", { name: "小川" })).toBeVisible();
  await expect(page.getByRole("link", { name: "小禾" })).toBeVisible();
  await page.getByRole("link", { name: "小宇" }).click();

  await expect(
    page.getByRole("heading", { name: "小宇的小文星球" }),
  ).toBeVisible();
  await expect(page.getByText("今日推荐")).toBeVisible();

  await page.goto("/children/s1/assessment");
  await page.getByLabel("升级前的句子").fill("公园很美。");
  await page
    .getByLabel("升级后的句子")
    .fill("公园里的花红红的，风一吹就轻轻摇。");
  await page
    .getByLabel("小写作")
    .fill(
      "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
    );
  await page.getByRole("button", { name: "完成小试炼" }).click();
  await expect(page.getByText("第一张能力草图")).toBeVisible();

  await page.goto("/children/s1/sentence");
  await page.getByLabel("原句").fill("公园很美。");
  await page
    .getByLabel("升级后的句子")
    .fill("清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。");
  await page.getByRole("button", { name: "提交给 AI 教练" }).click();
  await expect(page.getByText("加入了可看见的细节")).toBeVisible();

  await page.goto("/children/s1/essay");
  await page.getByLabel("作文题目").fill("我学会了骑车");
  await page
    .getByLabel("初稿")
    .fill("我学会了骑车。刚开始我很害怕。后来我会了。我很开心。");
  await page.getByRole("button", { name: "获得点评" }).click();
  await expect(page.getByText("给第二段加一个动作描写")).toBeVisible();
  await page
    .getByLabel("二稿")
    .fill(
      "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松开手后，我摇摇晃晃骑过花坛。",
    );
  await page.getByRole("button", { name: "提交二稿" }).click();
  await expect(page.getByText("细节更多")).toBeVisible();

  await page.goto("/parent/s1/report");
  await expect(page.getByRole("heading", { name: "阶段报告" })).toBeVisible();
  await expect(page.getByText("继续做 1 次句子加细节")).toBeVisible();
});
