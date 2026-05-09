import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import AssessmentPage from "../src/app/children/[studentId]/assessment/page";
import SentencePage from "../src/app/children/[studentId]/sentence/page";

afterEach(() => {
  cleanup();
});

vi.mock("../src/lib/api", () => ({
  createAssessment: async () => ({
    assessment: { summary: "完成入门小试炼，生成第一张能力草图。" },
  }),
  createSentenceTraining: async () => ({
    feedback: {
      encouragement: "你把画面写得更清楚了。",
      specific_improvement: "加入了可看见的细节",
    },
    settlement: {
      xp_delta: 25,
      level_after: 2,
      badge_code: "first_sentence_upgrade",
    },
  }),
}));

test("assessment page submits entry trial", async () => {
  render(<AssessmentPage params={{ studentId: "s1" }} />);

  await userEvent.type(screen.getByLabelText("升级前的句子"), "公园很美。");
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "公园里的花红红的，风一吹就轻轻摇。",
  );
  await userEvent.type(
    screen.getByLabelText("小写作"),
    "我学会了骑车。刚开始我很害怕，后来爸爸扶着我练，我终于能骑一小段了。",
  );
  await userEvent.click(screen.getByRole("button", { name: "完成小试炼" }));

  expect(
    await screen.findByText("完成入门小试炼，生成第一张能力草图。"),
  ).toBeInTheDocument();
});

test("sentence page shows ai feedback and settlement", async () => {
  render(<SentencePage params={{ studentId: "s1" }} />);

  await userEvent.type(screen.getByLabelText("原句"), "公园很美。");
  await userEvent.type(
    screen.getByLabelText("升级后的句子"),
    "清晨的公园里，荷叶上的水珠一闪一闪，像小灯泡。",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "提交给 AI 教练" }),
  );

  expect(await screen.findByText("加入了可看见的细节")).toBeInTheDocument();
  expect(screen.getByText("+25 XP")).toBeInTheDocument();
});
