import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import EssayPage from "../src/app/children/[studentId]/essay/page";
import ReadingPage from "../src/app/children/[studentId]/reading/page";
import ReportPage from "../src/app/parent/[studentId]/report/page";

vi.mock("../src/lib/api", () => ({
  createEssay: async () => ({
    essay: { id: "e1" },
    feedback: {
      strengths: ["能写清楚发生了什么", "有一处心情表达"],
      revision_tasks: [
        { instruction: "给第二段加一个动作描写", target: "第二段" },
      ],
    },
  }),
  submitEssayRevision: async () => ({
    comparison: {
      encouragement: "你把最重要的画面写清楚了。",
      improved_dimensions: ["细节更多", "动作更具体"],
    },
    settlement: { xp_delta: 60, level_after: 2, badge_code: "first_revision" },
  }),
  createReadingSession: async () => ({ transfer_tip: "写景时可以加入声音。" }),
  createReport: async () => ({
    content: {
      practice_summary: "本阶段完成了 1 次句子训练和 1 次阅读练习。",
      ability_changes: ["写具体力有新的证据"],
      best_revision: "我紧紧抓着车把，手心都出汗了。",
      weak_points: ["作文结构还需要更清楚"],
      next_suggestions: ["继续做 1 次句子加细节"],
    },
  }),
}));

test("essay page supports draft feedback and revision settlement", async () => {
  render(<EssayPage params={{ studentId: "s1" }} />);

  await userEvent.type(screen.getByLabelText("作文题目"), "我学会了骑车");
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕。后来我会了。我很开心。",
  );
  await userEvent.click(screen.getByRole("button", { name: "获得点评" }));
  expect(await screen.findByText("给第二段加一个动作描写")).toBeInTheDocument();

  await userEvent.type(
    screen.getByLabelText("二稿"),
    "我学会了骑车。刚开始我紧紧抓着车把，手心都出汗了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "提交二稿" }));
  expect(await screen.findByText("细节更多")).toBeInTheDocument();
});

test("reading page shows transfer tip", async () => {
  render(<ReadingPage params={{ studentId: "s1" }} />);

  await userEvent.click(screen.getByRole("button", { name: "提交阅读答案" }));

  expect(await screen.findByText("写景时可以加入声音。")).toBeInTheDocument();
});

test("report page renders parent-safe stage report", async () => {
  render(await ReportPage({ params: Promise.resolve({ studentId: "s1" }) }));

  expect(
    await screen.findByText("本阶段完成了 1 次句子训练和 1 次阅读练习。"),
  ).toBeInTheDocument();
  expect(screen.getByText("继续做 1 次句子加细节")).toBeInTheDocument();
});
