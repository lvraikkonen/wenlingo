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
  await page.getByLabel("孩子怎么称呼？").fill("小流");
  await page.getByLabel("孩子现在几年级？").selectOption("4");
  await page.getByRole("button", { name: "创建孩子档案" }).click();
  await expect(
    page.getByRole("heading", { name: "小流已加入小文星球！" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "进入小文星球" }).click();
  await expect(page.getByRole("heading", { name: "小流的小文星球" })).toBeVisible();
}

async function enterWritingCastle(page: Page) {
  await page
    .getByRole("navigation", { name: "Alpha 导航" })
    .getByRole("link", { name: "作文城堡" })
    .click();
  await expect(page.getByRole("heading", { name: "作文城堡" })).toBeVisible();
}

async function startClassroomNarrative(page: Page, title: string) {
  await page.getByRole("button", { name: "课内同步作文" }).click();
  await page.getByLabel("老师作文题目").fill(title);
  const classroomResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/writing-castle/classroom"),
  );
  await page.getByRole("button", { name: "开始审题" }).click();
  expect((await classroomResponse).ok()).toBeTruthy();

  const narrativeButton = page.getByRole("button", { name: "写一件事" });
  await expect(narrativeButton).toBeEnabled({ timeout: 15_000 });
  await narrativeButton.click();
  await expect(page.getByText("第 1 步 / 共 4 步：看懂题目")).toBeVisible({
    timeout: 15_000,
  });
}

async function continueToMaterialQuestions(page: Page) {
  await page.getByLabel("我觉得这题最重要的是").fill("写清楚事情的经过和感受");
  await page.getByRole("button", { name: "继续想素材" }).click();
  await expect(page.getByText("第 2 步 / 共 4 步：想一想素材")).toBeVisible({
    timeout: 15_000,
  });
}

async function fillFirstMaterialAnswer(page: Page, answer: string) {
  const materialStep = page.locator("section", {
    hasText: "第 2 步 / 共 4 步：想一想素材",
  });
  await materialStep.locator("textarea").first().fill(answer);
}

async function expectProgressOrCompleted(
  page: Page,
  progressText: string | RegExp,
  completedText: string | RegExp,
) {
  await expect(
    page.getByText(progressText).or(page.getByText(completedText)),
  ).toBeVisible({ timeout: 15_000 });
}

function streamingFlagsEnabled() {
  return (
    process.env.ESSAY_FEEDBACK_STREAMING_ENABLED === "true" &&
    process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED === "true"
  );
}

function prewritingJobFlagsEnabled() {
  return (
    process.env.PREWRITING_PROGRESS_JOBS_ENABLED === "true" &&
    process.env.NEXT_PUBLIC_PREWRITING_PROGRESS_JOBS_ENABLED === "true"
  );
}

test("direct draft reaches feedback with streaming enabled", async ({ page }) => {
  test.skip(!streamingFlagsEnabled(), "V0.6e streaming flags are disabled.");

  await createChild(page, "v06e-direct-stream@example.com", "V06E-DIRECT-STREAM");
  await enterWritingCastle(page);
  await page.getByRole("button", { name: "直接写初稿" }).click();
  await page.getByLabel("作文题目").fill("我学会了游泳");
  await page
    .getByLabel("初稿")
    .fill(
      "我学会了游泳。刚开始我很怕水，只敢扶着池边。教练教我先憋气，再慢慢打腿。后来我能游到对面，心里特别高兴。",
    );

  const streamResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/api/students/") &&
      response.url().includes("/essays/stream-feedback"),
  );
  await page.getByRole("button", { name: "获得点评" }).click();

  expect((await streamResponse).ok()).toBeTruthy();
  await expect(page.getByLabel("作文点评")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
});

test("Writing Castle first draft reaches feedback with streaming enabled", async ({
  page,
}) => {
  test.skip(!streamingFlagsEnabled(), "V0.6e streaming flags are disabled.");

  await createChild(
    page,
    "v06e-castle-stream@example.com",
    "V06E-CASTLE-STREAM",
  );
  await enterWritingCastle(page);
  await startClassroomNarrative(page, "一次勇敢的尝试");
  await continueToMaterialQuestions(page);
  await fillFirstMaterialAnswer(page, "我想写第一次参加朗读比赛。");
  await page.getByRole("button", { name: "我想直接开始写" }).click();
  await expect(page.getByLabel("初稿")).toBeVisible({ timeout: 15_000 });
  await page
    .getByLabel("初稿")
    .fill(
      "一次勇敢的尝试是参加朗读比赛。上台前我很紧张，手心出了汗。轮到我时，我深吸一口气，把每一句都读清楚。结束后老师鼓励了我，我觉得自己变勇敢了。",
    );

  const streamResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/first-draft/stream-feedback"),
  );
  await page.getByRole("button", { name: "提交初稿给 AI 教练" }).click();

  expect((await streamResponse).ok()).toBeTruthy();
  await expect(page.getByLabel("作文点评")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
});

test("material cards and outline show progress job states", async ({ page }) => {
  test.skip(!prewritingJobFlagsEnabled(), "V0.6e prewriting job flags are disabled.");

  await createChild(page, "v06e-prewriting-jobs@example.com", "V06E-JOBS");
  await enterWritingCastle(page);
  await startClassroomNarrative(page, "一件让我自豪的事");
  await continueToMaterialQuestions(page);
  await fillFirstMaterialAnswer(
    page,
    "我想写自己坚持练习跳绳，最后一分钟跳过了一百下。",
  );

  const materialJobResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/material-cards/jobs"),
  );
  await page.getByRole("button", { name: "整理素材卡" }).click();
  await expectProgressOrCompleted(
    page,
    /素材卡排队中|AI 正在整理素材卡|素材卡生成有点慢|正在切换备用方式整理素材卡|素材卡整理完成/,
    "第 3 步 / 共 4 步：整理素材卡",
  );
  const materialJob = await materialJobResponse;
  expect(materialJob.ok()).toBeTruthy();
  expect(await materialJob.json()).toEqual(
    expect.objectContaining({
      task_name: "material_card_generation",
      status: expect.stringMatching(/queued|running|completed/),
    }),
  );
  await expect(page.getByText("第 3 步 / 共 4 步：整理素材卡")).toBeVisible({
    timeout: 15_000,
  });

  const outlineJobResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().includes("/outline/jobs"),
  );
  await page.getByRole("button", { name: "生成提纲" }).click();
  await expectProgressOrCompleted(
    page,
    /提纲排队中|AI 正在搭提纲|提纲生成有点慢|正在切换备用方式搭提纲|提纲完成/,
    "第 4 步 / 共 4 步：搭一个提纲",
  );
  const outlineJob = await outlineJobResponse;
  expect(outlineJob.ok()).toBeTruthy();
  expect(await outlineJob.json()).toEqual(
    expect.objectContaining({
      task_name: "outline_generation",
      status: expect.stringMatching(/queued|running|completed/),
    }),
  );
  await expect(page.getByText("第 4 步 / 共 4 步：搭一个提纲")).toBeVisible({
    timeout: 15_000,
  });
});

test("feature flags disabled keep JSON behavior working", async ({ page }) => {
  test.skip(streamingFlagsEnabled(), "V0.6e streaming flags are enabled.");

  await createChild(page, "v06e-json-fallback@example.com", "V06E-JSON");
  await enterWritingCastle(page);
  await page.getByRole("button", { name: "直接写初稿" }).click();
  await page.getByLabel("作文题目").fill("我照顾小妹妹");
  await page
    .getByLabel("初稿")
    .fill(
      "我照顾小妹妹。妈妈做饭的时候，我陪妹妹搭积木。她想哭时，我拿玩具逗她笑。后来妈妈夸我很有耐心。",
    );

  const jsonResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/students\/[^/]+\/essays$/.test(new URL(response.url()).pathname),
  );
  await page.getByRole("button", { name: "获得点评" }).click();

  expect((await jsonResponse).ok()).toBeTruthy();
  await expect(page.getByLabel("作文点评")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
});
