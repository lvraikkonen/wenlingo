import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";

function seedAlphaInvite(email: string, inviteCode: string) {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      [
        "import sys",
        "from sqlalchemy import delete",
        "from sqlmodel import Session, select",
        "from app.api.routes.alpha import hash_invite_code",
        "from app.db.session import engine",
        "from app.domain.models import AlphaInviteCode, AuthMagicCode, ParentAccount, ParentSession, ParentUser",
        "email = sys.argv[1]",
        "invite_code = sys.argv[2]",
        "with Session(engine) as session:",
        "    accounts = session.exec(select(ParentAccount).where(ParentAccount.email_normalized == email)).all()",
        "    account_ids = [account.id for account in accounts]",
        "    if account_ids:",
        "        linked_parents = session.exec(select(ParentUser).where(ParentUser.account_id.in_(account_ids))).all()",
        "        for parent in linked_parents:",
        "            parent.account_id = None",
        "            parent.account_linked_at = None",
        "            session.add(parent)",
        "        session.execute(delete(ParentSession).where(ParentSession.account_id.in_(account_ids)))",
        "    session.execute(delete(AuthMagicCode).where(AuthMagicCode.email_normalized == email))",
        "    for account in accounts:",
        "        session.delete(account)",
        "    code_hash = hash_invite_code(invite_code)",
        "    invite = session.exec(select(AlphaInviteCode).where(AlphaInviteCode.code_hash == code_hash)).first()",
        "    if invite is None:",
        "        invite = AlphaInviteCode(code_hash=code_hash, label=f'E2E {invite_code}')",
        "    invite.status = 'issued'",
        "    invite.consumed_by_parent_id = None",
        "    invite.consumed_at = None",
        "    session.add(invite)",
        "    session.commit()",
      ].join("\n"),
      email,
      inviteCode,
    ],
    {
      cwd: "../api",
      env: {
        ...process.env,
        DATABASE_URL:
          process.env.PLAYWRIGHT_DATABASE_URL ?? "sqlite:///./playwright-e2e.db",
      },
    },
  );
}

async function createChild(page: Page, email: string, inviteCode: string) {
  seedAlphaInvite(email, inviteCode);

  await page.goto("/alpha/start");
  await expect(
    page.getByRole("heading", { name: "小文星球 WenLingo" }),
  ).toBeVisible();
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("内测邀请码").fill(inviteCode);
  await page.getByRole("button", { name: "获取验证码" }).click();
  await page.getByLabel("6 位验证码").fill("123456");
  await page.getByRole("button", { name: "继续使用 Alpha" }).click();
  await expect(page).toHaveURL(/\/parent\/children/);

  await page.getByRole("link", { name: "创建孩子档案" }).click();
  await page.getByLabel("孩子怎么称呼？").fill("小城");
  await page.getByLabel("孩子现在几年级？").selectOption("4");
  await page.getByRole("button", { name: "创建孩子档案" }).click();
  await expect(
    page.getByRole("heading", { name: "小城已加入小文星球！" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "进入小文星球" }).click();
  await expect(page.getByRole("heading", { name: "小城的小文星球" })).toBeVisible();
}

async function enterWritingCastle(page: Page) {
  await page
    .getByRole("navigation", { name: "Alpha 导航" })
    .getByRole("link", { name: "作文城堡" })
    .click();
  await expect(page.getByRole("heading", { name: "作文城堡" })).toBeVisible();
}

test("classroom writing castle reaches first draft feedback", async ({
  page,
}) => {
  await createChild(page, "v06a-classroom@example.com", "V06A-CLASSROOM");

  await enterWritingCastle(page);
  await page.getByRole("button", { name: "课内同步作文" }).click();
  await page.getByLabel("老师作文题目").fill("我学会了骑车");
  await page.getByRole("button", { name: "开始审题" }).click();

  await expect(page.getByText("第 1 步 / 共 4 步：看懂题目")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByLabel("我觉得这题最重要的是").fill("写清楚学会骑车的过程");
  await page.getByRole("button", { name: "继续想素材" }).click();

  await expect(page.getByText("第 2 步 / 共 4 步：想一想素材")).toBeVisible({
    timeout: 15_000,
  });
  await page
    .getByLabel("这件事是怎么开始的？")
    .fill("爸爸在小区空地扶着我练骑车。");
  await page.getByRole("button", { name: "整理素材卡" }).click();

  await expect(page.getByText("第 3 步 / 共 4 步：整理素材卡")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "生成提纲" }).click();

  await expect(page.getByText("第 4 步 / 共 4 步：搭一个提纲")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByLabel("结果").fill("最后我能自己骑过小区空地。");
  await page.getByRole("button", { name: "确认提纲，开始写" }).click();
  await expect(page.getByText("提纲提醒")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/最后我能自己骑过小区空地/)).toBeVisible();

  await page.reload();
  await expect(page.getByText("提纲提醒")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/最后我能自己骑过小区空地/)).toBeVisible();

  await page
    .getByLabel("初稿")
    .fill(
      "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。爸爸扶着后座陪我练，我摔倒后又站起来。后来我能自己骑一小段，心里特别开心。",
    );
  await page.getByRole("button", { name: "提交初稿给 AI 教练" }).click();

  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
});

test("direct draft essay path still reaches settlement", async ({ page }) => {
  await createChild(page, "v06a-direct@example.com", "V06A-DIRECT");

  await enterWritingCastle(page);
  await page.getByRole("button", { name: "直接写初稿" }).click();
  await page.getByLabel("作文题目").fill("我学会了骑车");
  await page
    .getByLabel("初稿")
    .fill(
      "我学会了骑车。刚开始我很害怕，手一直抓着车把。爸爸在旁边扶着我，我慢慢练习，最后能自己骑了。",
    );
  await page.getByRole("button", { name: "获得点评" }).click();

  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
  await page
    .getByLabel("二稿")
    .fill(
      "我学会了骑车。刚开始我很害怕，手一直紧紧抓着车把，脚也不敢用力。爸爸在旁边扶着我，提醒我眼睛看前方。我摔了一跤后没有放弃，又慢慢练习，最后能自己骑过小区空地了。",
    );
  await page.getByRole("button", { name: "提交二稿" }).click();

  await expect(page.getByText(/完成 .* 个修改任务/)).toBeVisible({
    timeout: 15_000,
  });
});
