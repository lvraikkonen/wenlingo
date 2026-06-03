import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";

function seedAlphaAuthSmokeData() {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      [
        "import os",
        "from datetime import datetime, timezone",
        "from sqlalchemy import delete",
        "from sqlmodel import Session, create_engine, select",
        "from app.api.routes.alpha import hash_invite_code",
        "from app.domain.models import AlphaInviteCode, AuthMagicCode, ParentAccount, ParentSession, ParentUser",
        "NEW_EMAIL = 'parent@example.com'",
        "LEGACY_PARENT_ID = 'legacy-e2e-parent'",
        "engine = create_engine(os.environ['DATABASE_URL'])",
        "def ensure_invite(session, code, label, status, consumed_by_parent_id=None):",
        "    code_hash = hash_invite_code(code)",
        "    invite = session.exec(select(AlphaInviteCode).where(AlphaInviteCode.code_hash == code_hash)).first()",
        "    if invite is None:",
        "        invite = AlphaInviteCode(code_hash=code_hash, label=label)",
        "    invite.label = label",
        "    invite.status = status",
        "    invite.consumed_by_parent_id = consumed_by_parent_id",
        "    invite.consumed_at = datetime.now(timezone.utc) if consumed_by_parent_id else None",
        "    session.add(invite)",
        "    return invite",
        "with Session(engine) as session:",
        "    accounts = session.exec(select(ParentAccount).where(ParentAccount.email_normalized == NEW_EMAIL)).all()",
        "    account_ids = [account.id for account in accounts]",
        "    if account_ids:",
        "        linked_parents = session.exec(select(ParentUser).where(ParentUser.account_id.in_(account_ids))).all()",
        "        for parent in linked_parents:",
        "            parent.account_id = None",
        "            parent.account_linked_at = None",
        "            session.add(parent)",
        "        session.execute(delete(ParentSession).where(ParentSession.account_id.in_(account_ids)))",
        "    session.execute(delete(AuthMagicCode).where(AuthMagicCode.email_normalized == NEW_EMAIL))",
        "    for account in accounts:",
        "        session.delete(account)",
        "    legacy_parent = session.get(ParentUser, LEGACY_PARENT_ID)",
        "    if legacy_parent is None:",
        "        legacy_parent = ParentUser(id=LEGACY_PARENT_ID, email='legacy-e2e-parent@example.com', display_name='Legacy E2E Parent')",
        "    legacy_parent.account_id = None",
        "    legacy_parent.account_linked_at = None",
        "    session.add(legacy_parent)",
        "    ensure_invite(session, 'ALPHA-E2E', 'E2E alpha invite', 'issued')",
        "    ensure_invite(session, 'LEGACY-E2E', 'E2E legacy invite', 'consumed', LEGACY_PARENT_ID)",
        "    session.commit()",
      ].join("\n"),
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

test.beforeEach(() => {
  seedAlphaAuthSmokeData();
});

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
