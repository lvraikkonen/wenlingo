import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";

type EssayArchiveItem = {
  essay_id: string;
  title: string;
  topic_origin: string;
  generated_topic_metadata: Record<string, unknown> | null;
  latest_round_index: number;
  hidden_by: string;
  can_continue_revision: boolean;
};

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

  return currentStudentId(page);
}

async function enterWritingCastle(page: Page) {
  await page
    .getByRole("navigation", { name: "Alpha 导航" })
    .getByRole("link", { name: "作文城堡" })
    .click();
  await expect(page.getByRole("heading", { name: "作文城堡" })).toBeVisible();
}

function currentStudentId(page: Page) {
  const match = page.url().match(/\/children\/([^/]+)/);
  if (!match) {
    throw new Error(`Could not read student id from ${page.url()}`);
  }

  return decodeURIComponent(match[1]);
}

async function submitDirectFirstDraft(
  page: Page,
  title: string,
  draft: string,
) {
  await page.getByRole("button", { name: "直接写初稿" }).click();
  await page.getByLabel("作文题目").fill(title);
  await page.getByLabel("初稿").fill(draft);
  await page.getByRole("button", { name: "获得点评" }).click();
  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
}

async function openArchiveDrawer(page: Page) {
  const drawer = page.getByRole("complementary", {
    name: "作文档案",
    hidden: true,
  });

  await page.getByRole("button", { name: "作文档案" }).click();
  await expect(drawer).toHaveAttribute("aria-hidden", "false");

  return drawer;
}

async function selectArchiveEssay(page: Page, title: string | RegExp) {
  const drawer = await openArchiveDrawer(page);
  const archiveItem = drawer.getByRole("button", { name: title });
  await expect(archiveItem).toBeVisible({ timeout: 15_000 });
  await archiveItem.click();
  await expect(page.getByLabel("下一稿")).toBeVisible({ timeout: 15_000 });
}

async function fetchChildArchive(page: Page, studentId: string) {
  const response = await page.request.get(
    `/api/students/${studentId}/essay-archive?limit=3`,
  );
  expect(response.ok()).toBeTruthy();

  return (await response.json()) as { items: EssayArchiveItem[] };
}

async function fetchParentArchive(page: Page, studentId: string) {
  const response = await page.request.get(
    `/api/parents/students/${studentId}/essay-archive?include_hidden=true&limit=20`,
  );
  expect(response.ok()).toBeTruthy();

  return (await response.json()) as { items: EssayArchiveItem[] };
}

async function expectArchiveItem(
  page: Page,
  studentId: string,
  title: string,
) {
  await expect
    .poll(async () => {
      const archive = await fetchChildArchive(page, studentId);
      return archive.items.find((item) => item.title === title) ?? null;
    })
    .not.toBeNull();

  const archive = await fetchChildArchive(page, studentId);
  const item = archive.items.find((candidate) => candidate.title === title);
  if (!item) {
    throw new Error(`Expected archive item for ${title}`);
  }

  return item;
}

async function expectDrawerAnchoredRight(page: Page) {
  const drawer = page.getByRole("complementary", {
    name: "作文档案",
    hidden: true,
  });
  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  if (!viewport) {
    return;
  }

  await expect
    .poll(async () => {
      const box = await drawer.boundingBox();
      if (!box) {
        return Number.POSITIVE_INFINITY;
      }
      return Math.abs(viewport.width - (box.x + box.width));
    })
    .toBeLessThan(2);

  const box = await drawer.boundingBox();
  expect(box).not.toBeNull();
  if (!box) {
    return;
  }
  expect(Math.abs(viewport.width - (box.x + box.width))).toBeLessThan(2);
  expect(box.x).toBeGreaterThanOrEqual(0);
}

async function continuePrewritingToDraft(page: Page, material: string) {
  await expect(page.getByText("第 1 步 / 共 4 步：看懂题目")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByLabel("我觉得这题最重要的是").fill("先写清楚一件真实的小事");
  await page.getByRole("button", { name: "继续想素材" }).click();

  const materialStep = page.locator("section", {
    hasText: "第 2 步 / 共 4 步：想一想素材",
  });
  await expect(materialStep).toBeVisible({ timeout: 15_000 });
  await materialStep.locator("textarea").first().fill(material);
  await materialStep.getByRole("button", { name: "我想直接开始写" }).click();

  await expect(page.getByLabel("初稿")).toBeVisible({ timeout: 15_000 });
}

async function submitPrewritingFirstDraft(
  page: Page,
  draft: string,
) {
  await page.getByLabel("初稿").fill(draft);
  await page.getByRole("button", { name: "提交初稿给 AI 教练" }).click();
  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
}

async function submitNextDraft(page: Page, content: string) {
  await page.getByLabel("下一稿").fill(content);
  await page.getByRole("button", { name: "提交下一稿" }).click();
  await expect(page.getByLabel("修改对比")).toBeVisible({ timeout: 15_000 });
}

test("classroom writing castle reaches first draft feedback", async ({
  page,
}) => {
  await createChild(page, "v06a-classroom@example.com", "V06A-CLASSROOM");

  await enterWritingCastle(page);
  await page.getByRole("button", { name: "课内同步作文" }).click();
  await page.getByLabel("老师作文题目").fill("我的“自画像”");
  await page.getByRole("button", { name: "开始审题" }).click();

  await expect(page.getByText("选择作文类型")).toBeVisible();
  await page.getByRole("button", { name: "写一个人" }).click();
  await expect(page.getByText("第 1 步 / 共 4 步：看懂题目")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByLabel("我觉得这题最重要的是").fill("写清楚自己的样子和特点");
  await page.getByRole("button", { name: "继续想素材" }).click();

  await expect(page.getByText("第 2 步 / 共 4 步：想一想素材")).toBeVisible({
    timeout: 15_000,
  });
  await page
    .getByLabel("写谁可以怎么写？")
    .fill("我要写我自己，四年级，喜欢画画。");
  await page.getByRole("button", { name: "整理素材卡" }).click();

  await expect(page.getByText("第 3 步 / 共 4 步：整理素材卡")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByLabel("写谁").fill("我自己，短头发，喜欢观察别人。");
  await page.getByRole("button", { name: "生成提纲" }).click();

  await expect(page.getByText("第 4 步 / 共 4 步：搭一个提纲")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByLabel("写感受或评价").fill("我觉得这样的自己很认真，也想更勇敢。");
  await page.getByRole("button", { name: "确认提纲，开始写" }).click();
  await expect(page.getByText("提纲提醒")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/我觉得这样的自己很认真/)).toBeVisible();

  await page.reload();
  await expect(page.getByText("提纲提醒")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/我觉得这样的自己很认真/)).toBeVisible();

  await page
    .getByLabel("初稿")
    .fill(
      "我的自画像里有一个爱观察的我。我留着短头发，平时喜欢画画，也喜欢把看到的小细节记下来。遇到困难时我会先想一想，再认真完成。我希望自己以后更勇敢。",
    );
  await page.getByRole("button", { name: "提交初稿给 AI 教练" }).click();

  await expect(page.getByText("修改小任务")).toBeVisible({ timeout: 15_000 });
});

test("v0.6c classroom new family reaches first draft feedback", async ({
  page,
}) => {
  await createChild(page, "v06c-classroom@example.com", "V06C-CLASSROOM");

  await enterWritingCastle(page);
  await page.getByRole("button", { name: "课内同步作文" }).click();
  await page.getByLabel("老师作文题目").fill("给老师写信");
  await page.getByRole("button", { name: "开始审题" }).click();

  await page.getByRole("button", { name: "写实用文" }).click();
  await expect(page.getByText("第 1 步 / 共 4 步：看懂题目")).toBeVisible({
    timeout: 15_000,
  });
});

test("v0.6c ai topic path generates and selects an idea", async ({ page }) => {
  await createChild(page, "v06c-ai-topic@example.com", "V06C-AI-TOPIC");

  await enterWritingCastle(page);
  await page.getByRole("button", { name: "AI 出题作文" }).click();
  await page.getByLabel("兴趣或想写的方向").fill("足球");
  await page.getByRole("button", { name: "生成题目灵感" }).click();

  const firstIdeaButton = page
    .getByRole("button", { name: "选择这个题目" })
    .first();
  await expect(firstIdeaButton).toBeVisible({ timeout: 15_000 });
  await firstIdeaButton.click();
  await expect(page.getByText("第 1 步 / 共 4 步：看懂题目")).toBeVisible({
    timeout: 15_000,
  });
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
    .getByLabel("下一稿")
    .fill(
      "我学会了骑车。刚开始我很害怕，手一直紧紧抓着车把，脚也不敢用力。爸爸在旁边扶着我，提醒我眼睛看前方。我摔了一跤后没有放弃，又慢慢练习，最后能自己骑过小区空地了。",
    );
  await page.getByRole("button", { name: "提交下一稿" }).click();

  await expect(page.getByText(/完成 .* 个修改任务/)).toBeVisible({
    timeout: 15_000,
  });
});

test("v0.6d direct draft can reset, restore from archive, and submit revision", async ({
  page,
}) => {
  const title = "我第一次做饭";
  const studentId = await createChild(
    page,
    "v06d-direct-restore@example.com",
    "V06D-DIRECT-RESTORE",
  );

  await enterWritingCastle(page);
  await submitDirectFirstDraft(
    page,
    title,
    "我第一次做饭时很紧张。我先洗菜，再把鸡蛋打进碗里。锅热起来以后，我慢慢翻炒，最后把菜端给妈妈看。",
  );

  await page.getByRole("button", { name: "写新的作文" }).first().click();
  await expect(page.getByLabel("作文题目")).toHaveValue("");
  await expect(page.getByLabel("初稿")).toHaveValue("");
  await expectArchiveItem(page, studentId, title);

  await selectArchiveEssay(page, title);
  await expect(page.getByLabel("下一稿")).toHaveValue(/我第一次做饭时很紧张/);
  await submitNextDraft(
    page,
    "我第一次做饭时很紧张。我先洗菜，把水甩干，再把鸡蛋轻轻打进碗里。锅热起来以后，我听见油滋滋响，就慢慢翻炒。最后我把菜端给妈妈看，心里很有成就感。",
  );

  await expect(page.getByText(/完成 .* 个修改任务/)).toBeVisible({
    timeout: 15_000,
  });
});

test("v0.6d writing castle prewriting first draft appears in archive", async ({
  page,
}) => {
  const title = "一次难忘的活动";
  const studentId = await createChild(
    page,
    "v06d-prewriting-archive@example.com",
    "V06D-PREWRITE",
  );

  await enterWritingCastle(page);
  await page.getByRole("button", { name: "课内同步作文" }).click();
  await page.getByLabel("老师作文题目").fill(title);
  await page.getByRole("button", { name: "开始审题" }).click();
  await page.getByRole("button", { name: "写一件事" }).click();
  await continuePrewritingToDraft(page, "我想写班级跳绳活动，我负责给同学加油。");
  await submitPrewritingFirstDraft(
    page,
    "一次难忘的活动是班级跳绳比赛。轮到我们组时，我站在旁边给同学加油，也认真数每一次跳绳。虽然大家有点紧张，但我们互相提醒，最后顺利完成了比赛。",
  );

  const drawer = await openArchiveDrawer(page);
  await expect(drawer.getByRole("button", { name: new RegExp(title) })).toBeVisible({
    timeout: 15_000,
  });
  const item = await expectArchiveItem(page, studentId, title);
  expect(item.topic_origin).toBe("teacher_provided");
});

test("v0.6d ai topic first draft preserves archive topic origin", async ({
  page,
}) => {
  const studentId = await createChild(
    page,
    "v06d-ai-topic-archive@example.com",
    "V06D-AI-TOPIC",
  );

  await enterWritingCastle(page);
  await page.getByRole("button", { name: "AI 出题作文" }).click();
  await page.getByLabel("兴趣或想写的方向").fill("足球");
  await page.getByRole("button", { name: "生成题目灵感" }).click();

  await expect(page.getByText("足球训练小挑战")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: "选择这个题目" }).first().click();
  await continuePrewritingToDraft(page, "我想写一次足球训练里练习射门的挑战。");
  await submitPrewritingFirstDraft(
    page,
    "足球训练小挑战让我记得很清楚。那天我练习射门，刚开始总是踢偏。教练提醒我要看准方向，我又试了几次，终于踢进了一球。",
  );

  const archiveItem = await expectArchiveItem(page, studentId, "足球训练小挑战");
  expect(archiveItem.topic_origin).toBe("ai_topic_idea");
  expect(archiveItem.generated_topic_metadata?.id).toBe("idea-1");
});

test("v0.6d multi-round revision reaches third draft with round-neutral copy", async ({
  page,
}) => {
  const title = "雨中的放学路";
  const studentId = await createChild(
    page,
    "v06d-multi-round@example.com",
    "V06D-MULTI",
  );

  await enterWritingCastle(page);
  await submitDirectFirstDraft(
    page,
    title,
    "雨中的放学路很湿。我背着书包往家走，路上有很多水。我看到同学也在慢慢走，大家都想快点回家。",
  );
  await submitNextDraft(
    page,
    "雨中的放学路很湿。我背着书包往家走，鞋底踩在水洼里发出啪啪声。我看到同学也在慢慢走，大家撑着伞，小心绕开路边的积水。",
  );

  const secondRoundItem = await expectArchiveItem(page, studentId, title);
  expect(secondRoundItem.latest_round_index).toBe(2);

  await selectArchiveEssay(page, title);
  await expect(page.getByText("正在写第 3 稿")).toBeVisible();
  await expect(page.getByLabel("下一稿")).toHaveValue(
    /鞋底踩在水洼里发出啪啪声/,
  );
  await expect(page.getByRole("button", { name: "提交下一稿" })).toBeVisible();
  await expect(page.getByRole("button", { name: "提交二稿" })).toHaveCount(0);

  await submitNextDraft(
    page,
    "雨中的放学路很湿。我背着书包往家走，鞋底踩在水洼里发出啪啪声。风把伞吹得有点歪，我扶紧伞柄，小心绕开路边的积水。到家时裤脚湿了，但我觉得自己很能坚持。",
  );
  const comparison = page.getByLabel("修改对比");
  await expect(comparison).toBeVisible();
  await expect(comparison).not.toContainText("二稿");
  await expect(page.locator("body")).not.toContainText("二稿");
  await expect(page.getByRole("button", { name: "提交二稿" })).toHaveCount(0);
});

test("v0.6d child hide, parent restore, and child archive refetch", async ({
  page,
}) => {
  const title = "藏起来再找回";
  const studentId = await createChild(
    page,
    "v06d-hide-restore@example.com",
    "V06D-HIDE",
  );

  await enterWritingCastle(page);
  await submitDirectFirstDraft(
    page,
    title,
    "这篇作文记录我整理书桌。我把铅笔放进笔筒，把旧草稿纸夹起来，还把课本按学科排好。整理完以后，桌面看起来清爽多了。",
  );

  const drawer = await openArchiveDrawer(page);
  await expectDrawerAnchoredRight(page);
  await expect(drawer.getByRole("button", { name: new RegExp(title) })).toBeVisible({
    timeout: 15_000,
  });
  await drawer.getByRole("button", { name: "暂时藏起这篇作文" }).click();
  await expect(drawer.getByRole("button", { name: new RegExp(title) })).toHaveCount(0);
  await page.getByRole("button", { name: "关闭作文档案" }).click();
  await expect(page.getByRole("button", { name: "关闭作文档案" })).toHaveCount(0);

  await expect
    .poll(async () => {
      const archive = await fetchChildArchive(page, studentId);
      return archive.items.some((item) => item.title === title);
    })
    .toBe(false);

  const parentArchive = await fetchParentArchive(page, studentId);
  const hiddenItem = parentArchive.items.find((item) => item.title === title);
  expect(hiddenItem?.hidden_by).toBe("child");

  await page
    .getByRole("navigation", { name: "Alpha 导航" })
    .getByRole("link", { name: "家长摘要" })
    .click();
  await expect(page.getByText("作文档案摘要")).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: `恢复作文：${title}` }).click();
  await expect(page.getByRole("button", { name: `恢复作文：${title}` })).toHaveCount(0, {
    timeout: 15_000,
  });

  await page.goto(`/children/${studentId}/essay`);
  await expect(page.getByRole("heading", { name: "作文城堡" })).toBeVisible();
  const restoredDrawer = await openArchiveDrawer(page);
  await expect(restoredDrawer.getByRole("button", { name: new RegExp(title) })).toBeVisible({
    timeout: 15_000,
  });
});

test("v0.6d mobile archive drawer opens from the right", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await createChild(page, "v06d-mobile-drawer@example.com", "V06D-MOBILE");

  await enterWritingCastle(page);
  await openArchiveDrawer(page);

  await expectDrawerAnchoredRight(page);
});
