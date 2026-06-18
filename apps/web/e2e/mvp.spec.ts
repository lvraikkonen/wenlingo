import { execFileSync } from "node:child_process";
import { expect, test, type BrowserContext } from "@playwright/test";

const ASSESSMENT_SESSION_TOKEN = "e2e-assessment-session";

test.use({
  baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000",
});

async function addApiSessionCookie(context: BrowserContext, token: string) {
  await context.addCookies([
    {
      name: "wenlingo_parent_session",
      value: token,
      url: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
}

function seedDefaultAssessmentChild() {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      [
        "import os",
        "from datetime import timedelta",
        "from sqlalchemy import delete",
        "from sqlmodel import Session, create_engine, select",
        "from app.domain.models import AbilityHistory, AbilityProfile, Assessment, Essay, EssayVersion, GameEvent, LLMCallLog, ParentAccount, ParentSession, ParentUser, ReadingSession, Report, SentenceTraining, StudentProfile, utcnow",
        "from app.services.auth_security import hash_secret",
        "STUDENT_ID = 'e2e-assessment-child'",
        "PARENT_ID = 'e2e-assessment-parent'",
        "ACCOUNT_EMAIL = 'e2e-assessment@example.com'",
        `SESSION_TOKEN = '${ASSESSMENT_SESSION_TOKEN}'`,
        "engine = create_engine(os.environ['DATABASE_URL'])",
        "with Session(engine) as session:",
        "    essay_ids = session.exec(select(Essay.id).where(Essay.student_id == STUDENT_ID)).all()",
        "    accounts = session.exec(select(ParentAccount).where(ParentAccount.email_normalized == ACCOUNT_EMAIL)).all()",
        "    account_ids = [account.id for account in accounts]",
        "    if account_ids:",
        "        session.execute(delete(ParentSession).where(ParentSession.account_id.in_(account_ids)))",
        "    for account in accounts:",
        "        session.delete(account)",
        "    session.execute(delete(Assessment).where(Assessment.student_id == STUDENT_ID))",
        "    session.execute(delete(AbilityHistory).where(AbilityHistory.student_id == STUDENT_ID))",
        "    session.execute(delete(GameEvent).where(GameEvent.student_id == STUDENT_ID))",
        "    session.execute(delete(ReadingSession).where(ReadingSession.student_id == STUDENT_ID))",
        "    session.execute(delete(Report).where(Report.student_id == STUDENT_ID))",
        "    session.execute(delete(SentenceTraining).where(SentenceTraining.student_id == STUDENT_ID))",
        "    if essay_ids:",
        "        session.execute(delete(EssayVersion).where(EssayVersion.essay_id.in_(essay_ids)))",
        "    session.execute(delete(Essay).where(Essay.student_id == STUDENT_ID))",
        "    session.execute(delete(LLMCallLog).where(LLMCallLog.student_id == STUDENT_ID))",
        "    session.execute(delete(AbilityProfile).where(AbilityProfile.student_id == STUDENT_ID))",
        "    session.execute(delete(StudentProfile).where(StudentProfile.id == STUDENT_ID))",
        "    session.execute(delete(ParentUser).where(ParentUser.id == PARENT_ID))",
        "    account = ParentAccount(email_normalized=ACCOUNT_EMAIL, email_verified_at=utcnow(), last_login_at=utcnow())",
        "    session.add(account)",
        "    session.flush()",
        "    parent = ParentUser(id=PARENT_ID, email=ACCOUNT_EMAIL, display_name='E2E Parent', account_id=account.id, account_linked_at=utcnow())",
        "    student = StudentProfile(id=STUDENT_ID, parent_id=parent.id, name='\\u5c0f\\u6d4b', persona='real_child', is_real_child=True)",
        "    ability = AbilityProfile(student_id=student.id)",
        "    parent_session = ParentSession(account_id=account.id, token_hash=hash_secret(SESSION_TOKEN, purpose='session-token', pepper='test-pepper'), expires_at=utcnow() + timedelta(days=30))",
        "    session.add(parent)",
        "    session.add(student)",
        "    session.add(ability)",
        "    session.add(parent_session)",
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

test("default child completes assessment and returns to non-assessment dashboard recommendation", async ({
  context,
  page,
}) => {
  seedDefaultAssessmentChild();
  await addApiSessionCookie(context, ASSESSMENT_SESSION_TOKEN);

  await page.goto("/children/e2e-assessment-child");

  await expect(page.getByRole("heading", { name: "小测的小文星球" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "入门小试炼" })).toBeVisible();
  await page
    .getByRole("article")
    .filter({ hasText: "入门小试炼" })
    .getByRole("link", { name: "开始任务" })
    .click();

  await expect(
    page.getByRole("heading", { name: "认识你的写作超能力" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "开始小试炼" }).click();
  await expect(page.getByText("公园很美。")).toBeVisible();
  await page
    .getByLabel("升级后的句子")
    .fill("公园里的花红红的，风一吹就轻轻摇。");
  await page.getByRole("button", { name: "继续写小作文" }).click();
  await page
    .getByLabel("小写作")
    .fill("我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。");
  await page.getByRole("button", { name: "生成能力草图" }).click();

  await expect(page.getByRole("heading", { name: "第一张能力草图" })).toBeVisible();
  await expect(
    page.getByRole("paragraph").filter({ hasText: /^写具体力$/ }),
  ).toBeVisible();
  await expect(page.getByText("等待阅读试炼")).toBeVisible();
  await expect(page.getByText("等待二稿试炼")).toBeVisible();

  await page.getByRole("link", { name: "回到 Dashboard" }).click();
  await expect(page.getByRole("heading", { name: "第一张能力草图" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "作文城堡" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "入门小试炼" })).toHaveCount(0);
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
  await page.getByRole("button", { name: "自己带句子来练" }).click();
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

  await expect(page.getByText("阅读峡谷 · 即将开放")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "小宇的小文星球" }),
  ).toBeVisible();
});
