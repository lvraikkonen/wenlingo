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

async function createAlphaFamily(page: Page, email: string, inviteCode: string) {
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
}

test("magic code login reaches parent children page", async ({ page }) => {
  await createAlphaFamily(page, "v05c-login@example.com", "V05C-LOGIN");
  await expect(page.getByRole("heading", { name: "我的孩子" })).toBeVisible();
});

test("new alpha child completes generated sentence challenge", async ({ page }) => {
  await createAlphaFamily(page, "v05c-sentence@example.com", "V05C-SENTENCE");

  await page.getByRole("link", { name: "创建孩子档案" }).click();
  await page.getByLabel("孩子怎么称呼？").fill("小测");
  await page.getByLabel("孩子现在几年级？").selectOption("4");
  await page.getByRole("button", { name: "创建孩子档案" }).click();
  await expect(page.getByRole("heading", { name: "小测已加入小文星球！" })).toBeVisible();

  await page.getByRole("link", { name: "进入小文星球" }).click();
  await expect(page.getByRole("heading", { name: "小测的小文星球" })).toBeVisible();
  await page
    .getByRole("article")
    .filter({ hasText: "句子工坊" })
    .getByRole("link", { name: "开始任务" })
    .click();

  await expect(page.getByRole("heading", { name: "句子工坊" })).toBeVisible();
  const submitToCoach = page.getByRole("button", { name: "提交给 AI 教练" });
  await expect(submitToCoach).toBeEnabled({ timeout: 15000 });
  await page.getByLabel("升级后的句子").fill("小猫弓起背，飞快地跑过草地。");
  await submitToCoach.click();
  await expect(
    page.getByRole("region", { name: "AI 教练反馈", exact: true }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("这是一个参考写法，你的写法也很棒。")).toBeVisible();
});
