import { expect, test } from "@playwright/test";

test.use({
  baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000",
});

test("family demo completes family-test readiness flow without manual URL edits", async ({
  page,
}) => {
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
  await expect(page.getByText("当前孩子：小宇")).toBeVisible();
  await expect(page.getByRole("link", { name: "小晴" })).toHaveAttribute(
    "href",
    "/children/s2",
  );

  await page
    .getByLabel("主导航")
    .getByRole("link", { name: "作文城堡" })
    .click();
  await page.getByLabel("作文题目").fill("我学会了骑车");
  await page
    .getByLabel("初稿")
    .fill("我学会了骑车。刚开始我很害怕。后来我会了。我很开心。");
  await page.getByRole("button", { name: "获得点评" }).click();
  await expect(page.getByText("给第二段加一个动作描写")).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "给第二段加一个动作描写" }),
  ).toBeChecked();
  await page
    .getByLabel("二稿")
    .fill(
      "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。爸爸松开手后，我摇摇晃晃骑过花坛。",
    );
  await page.getByRole("button", { name: "提交二稿" }).click();
  await expect(page.getByText("你把最重要的画面写清楚了。")).toBeVisible();
  await expect(page.getByText("完成 1 个修改任务")).toBeVisible();

  await page.getByRole("link", { name: "Dashboard" }).click();
  await page
    .getByRole("article")
    .filter({ hasText: "句子工坊" })
    .getByRole("link", { name: "开始任务" })
    .click();
  await page.getByLabel("原句").fill("公园很美。");
  await page
    .getByLabel("升级后的句子")
    .fill("清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。");
  await page.getByRole("button", { name: "提交给 AI 教练" }).click();
  await expect(page.getByText("加入了可看见的细节")).toBeVisible();
  await expect(page.getByText("+25 XP")).toBeVisible();

  await page.getByRole("link", { name: "给家长看报告" }).click();
  await expect(page.getByRole("heading", { name: "阶段报告" })).toBeVisible();
  await expect(page.getByText("完成了 1 个修改任务")).toBeVisible();
  await page.getByRole("link", { name: "回到当前孩子 Dashboard" }).click();

  await page.getByRole("link", { name: "阅读峡谷" }).click();
  await expect(
    page.getByRole("heading", { name: "阅读峡谷施工中" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "回到小文星球" }).click();
  await expect(
    page.getByRole("heading", { name: "小宇的小文星球" }),
  ).toBeVisible();
});
