import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Suspense } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import EssayPage from "../src/app/children/[studentId]/essay/page";

const apiMocks = vi.hoisted(() => ({
  createClassroomWritingCastleEssay: vi.fn(),
  generateTopicAnalysis: vi.fn(),
  saveTopicFocus: vi.fn(),
  generateMaterialQuestions: vi.fn(),
  saveMaterialAnswers: vi.fn(),
  generateMaterialCards: vi.fn(),
  saveMaterialCards: vi.fn(),
  generateOutline: vi.fn(),
  saveOutline: vi.fn(),
  submitPrewritingFirstDraft: vi.fn(),
  createEssay: vi.fn(),
  submitEssayRevision: vi.fn(),
}));

function essayState(overrides = {}) {
  return {
    id: "essay-1",
    student_id: "student-1",
    title: "我学会了骑车",
    status: "prewriting_started",
    material_card: {
      schema_version: "v0.6a.1",
      questions: [],
      answers: [],
      cards: [],
      step_state: {
        questions_status: "not_started",
        cards_status: "not_started",
      },
    },
    outline: {
      schema_version: "v0.6a.1",
      topic_analysis: { cards: [], suggested_focus: "", status: "not_started" },
      child_topic_focus: {
        text: "",
        adopted_from_ai: false,
        skipped: false,
        updated_at: "",
      },
      sections: [],
      step_state: { outline_status: "not_started" },
    },
    ...overrides,
  };
}

vi.mock("../src/lib/api", () => ({
  createClassroomWritingCastleEssay: apiMocks.createClassroomWritingCastleEssay,
  generateTopicAnalysis: apiMocks.generateTopicAnalysis,
  saveTopicFocus: apiMocks.saveTopicFocus,
  generateMaterialQuestions: apiMocks.generateMaterialQuestions,
  saveMaterialAnswers: apiMocks.saveMaterialAnswers,
  generateMaterialCards: apiMocks.generateMaterialCards,
  saveMaterialCards: apiMocks.saveMaterialCards,
  generateOutline: apiMocks.generateOutline,
  saveOutline: apiMocks.saveOutline,
  submitPrewritingFirstDraft: apiMocks.submitPrewritingFirstDraft,
  createEssay: apiMocks.createEssay,
  submitEssayRevision: apiMocks.submitEssayRevision,
}));

beforeEach(() => {
  apiMocks.createClassroomWritingCastleEssay.mockResolvedValue({
    essay: essayState(),
  });
  apiMocks.generateTopicAnalysis.mockResolvedValue({
    essay: essayState({
      outline: {
        ...essayState().outline,
        topic_analysis: {
          status: "generated",
          suggested_focus: "写清楚学会骑车的过程",
          cards: [
            {
              id: "topic-ask",
              kind: "topic_question",
              title: "题目在问什么",
              body: "写一次真实经历。",
              required_points: [],
            },
            {
              id: "must-have",
              kind: "must_include",
              title: "一定要写到什么",
              body: "写清楚经过。",
              required_points: ["经过"],
            },
            {
              id: "shine",
              kind: "shine_point",
              title: "可以写精彩的地方",
              body: "写一个动作。",
              required_points: [],
            },
          ],
        },
      },
    }),
  });
  apiMocks.saveTopicFocus.mockResolvedValue({
    essay: essayState({ status: "topic_ready" }),
  });
  apiMocks.generateMaterialQuestions.mockResolvedValue({
    essay: essayState({
      material_card: {
        ...essayState().material_card,
        questions: [
          {
            id: "q-event",
            text: "你想写哪件真实发生的事？",
            hint: "写一句就可以",
            order: 1,
          },
          {
            id: "q-detail",
            text: "哪个画面最清楚？",
            hint: "写动作或声音",
            order: 2,
          },
          {
            id: "q-feeling",
            text: "你有什么感受？",
            hint: "可以跳过",
            order: 3,
          },
        ],
      },
    }),
  });
  apiMocks.saveMaterialAnswers.mockResolvedValue({
    essay: essayState({ status: "materials_ready" }),
  });
  apiMocks.generateMaterialCards.mockResolvedValue({
    essay: essayState({
      material_card: {
        ...essayState().material_card,
        cards: [
          {
            id: "card-event",
            category: "event",
            text: "我学会了骑车。",
            source_answer_ids: ["answer-q-event"],
            order: 1,
            deleted: false,
            child_edited: false,
            placeholder: false,
          },
          {
            id: "card-detail",
            category: "detail",
            text: "",
            source_answer_ids: [],
            order: 2,
            deleted: false,
            child_edited: false,
            placeholder: true,
          },
          {
            id: "card-feeling",
            category: "feeling_takeaway",
            text: "",
            source_answer_ids: [],
            order: 3,
            deleted: false,
            child_edited: false,
            placeholder: true,
          },
        ],
      },
    }),
  });
  apiMocks.saveMaterialCards.mockResolvedValue({
    essay: essayState({ status: "materials_ready" }),
  });
  apiMocks.generateOutline.mockResolvedValue({
    essay: essayState({
      outline: {
        ...essayState().outline,
        sections: [
          {
            id: "outline-cause",
            slot: "cause",
            heading: "起因",
            note: "",
            source_card_ids: [],
            child_edited: false,
            placeholder: true,
          },
          {
            id: "outline-process",
            slot: "process",
            heading: "经过",
            note: "我学会了骑车。",
            source_card_ids: ["card-event"],
            child_edited: false,
            placeholder: false,
          },
          {
            id: "outline-result",
            slot: "result",
            heading: "结果",
            note: "",
            source_card_ids: [],
            child_edited: false,
            placeholder: true,
          },
          {
            id: "outline-reflection",
            slot: "reflection",
            heading: "感受",
            note: "",
            source_card_ids: [],
            child_edited: false,
            placeholder: true,
          },
        ],
      },
    }),
  });
  apiMocks.saveOutline.mockResolvedValue({
    essay: essayState({ status: "outline_ready" }),
  });
  apiMocks.submitPrewritingFirstDraft.mockResolvedValue({
    essay: { id: "essay-1" },
    first_draft: {
      id: "draft-1",
      essay_id: "essay-1",
      version_label: "first_draft",
      reaction: null,
    },
    feedback: {
      strengths: ["能写清楚发生了什么", "有一处心情表达"],
      improvements: ["第二段缺少动作细节"],
      problem_monsters: ["细节缺口"],
      sentence_notes: ["把很开心换成动作。"],
      revision_tasks: [
        { instruction: "给第二段加一个动作描写", target: "第二段" },
      ],
    },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("classroom writing castle path reaches first draft feedback", async () => {
  await act(async () => {
    render(
      <Suspense fallback={null}>
        <EssayPage params={Promise.resolve({ studentId: "student-1" })} />
      </Suspense>,
    );
  });

  await userEvent.click(
    await screen.findByRole("button", { name: "课内同步作文" }),
  );
  await userEvent.type(screen.getByLabelText("老师作文题目"), "我学会了骑车");
  await userEvent.click(screen.getByRole("button", { name: "开始审题" }));
  expect(await screen.findByText("第 1 步 / 共 4 步：看懂题目")).toBeInTheDocument();
  expect(await screen.findByText("题目在问什么")).toBeInTheDocument();

  await userEvent.type(
    screen.getByLabelText("我觉得这题最重要的是"),
    "写清楚学会骑车的过程",
  );
  await userEvent.click(screen.getByRole("button", { name: "继续想素材" }));
  expect(
    await screen.findByText("第 2 步 / 共 4 步：想一想素材"),
  ).toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("你想写哪件真实发生的事？"),
    "我学会了骑车。",
  );
  await userEvent.click(screen.getByRole("button", { name: "整理素材卡" }));

  expect(
    await screen.findByText("第 3 步 / 共 4 步：整理素材卡"),
  ).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("事件"));
  await userEvent.type(screen.getByLabelText("事件"), "我学会了骑车，还摔了一跤。");
  await userEvent.click(screen.getByRole("button", { name: "生成提纲" }));

  expect(
    await screen.findByText("第 4 步 / 共 4 步：搭一个提纲"),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "确认提纲，开始写" }));
  await userEvent.type(
    screen.getByLabelText("初稿"),
    "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "提交初稿给 AI 教练" }),
  );

  expect(await screen.findByText("修改小任务")).toBeInTheDocument();
  expect(apiMocks.submitPrewritingFirstDraft).toHaveBeenCalledWith("essay-1", {
    draft:
      "我学会了骑车。刚开始我很害怕，手紧紧抓着车把。后来我慢慢练习，终于能自己骑了。我很开心。",
  });
});
