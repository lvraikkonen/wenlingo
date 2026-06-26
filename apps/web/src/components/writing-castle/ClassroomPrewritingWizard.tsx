"use client";

import { useEffect, useRef, useState } from "react";
import {
  createClassroomWritingCastleEssay,
  generateMaterialCards,
  generateMaterialQuestions,
  generateOutline,
  generateTopicAnalysis,
  getActiveClassroomWritingCastleEssay,
  saveMaterialAnswers,
  saveMaterialCards,
  saveOutline,
  saveTopicFocus,
  selectWritingCastleScaffold,
  submitPrewritingFirstDraft,
  type EssayResponse,
} from "../../lib/api";
import type {
  FutureTopicType,
  MaterialAnswer,
  MaterialCardSlot,
  TopicType,
  TopicTypeChoice,
  WritingCastleEssay,
  WritingOutlineSection,
} from "../../lib/types";
import { FirstDraftStep } from "./FirstDraftStep";
import { MaterialCardsStep } from "./MaterialCardsStep";
import { MaterialQuestionsStep } from "./MaterialQuestionsStep";
import { OutlineStep } from "./OutlineStep";
import { TopicAnalysisStep } from "./TopicAnalysisStep";

type Step =
  | "topic_entry"
  | "scaffold_selection"
  | "topic_analysis"
  | "questions"
  | "cards"
  | "outline"
  | "draft"
  | "feedback";

const DEFAULT_SUPPORTED_TOPIC_TYPES: TopicTypeChoice[] = [
  {
    topic_type: "generic_narrative",
    display_name_child: "写一件事",
    display_name_parent: "记叙一件事",
  },
  {
    topic_type: "person_portrait",
    display_name_child: "写一个人",
    display_name_parent: "人物描写",
  },
  {
    topic_type: "imaginative_story",
    display_name_child: "编一个想象故事",
    display_name_parent: "想象作文",
  },
  {
    topic_type: "expository_introduction",
    display_name_child: "介绍一种事物",
    display_name_parent: "说明介绍",
  },
];

function answersFromEssay(essay: WritingCastleEssay): MaterialAnswer[] {
  if (essay.material_card.answers.length > 0) {
    return essay.material_card.answers;
  }
  return essay.material_card.questions.map((question) => ({
    id: `answer-${question.id}`,
    question_id: question.id,
    text: "",
    skipped: false,
  }));
}

function stepFromEssay(essay: WritingCastleEssay): Step {
  if (
    essay.status === "outline_ready" ||
    essay.outline.step_state.outline_status === "confirmed" ||
    essay.outline.step_state.outline_status === "skipped"
  ) {
    return "draft";
  }
  if (essay.outline.sections.length > 0) {
    return "outline";
  }
  if (essay.material_card.cards.length > 0) {
    return "cards";
  }
  if (essay.material_card.questions.length > 0) {
    return "questions";
  }
  if (
    essay.outline.schema_version === "v0.6b.1" &&
    !essay.outline.scaffold
  ) {
    return "scaffold_selection";
  }
  if (essay.outline.topic_analysis.status === "generated") {
    return "topic_analysis";
  }
  return "topic_entry";
}

export function ClassroomPrewritingWizard({
  studentId,
  onFeedback,
}: {
  studentId: string;
  onFeedback: (result: EssayResponse) => void;
}) {
  const [step, setStep] = useState<Step>("topic_entry");
  const [topicText, setTopicText] = useState("");
  const [essay, setEssay] = useState<WritingCastleEssay | null>(null);
  const [focus, setFocus] = useState("");
  const [suggestedFocus, setSuggestedFocus] = useState("");
  const [answers, setAnswers] = useState<MaterialAnswer[]>([]);
  const [cards, setCards] = useState<MaterialCardSlot[]>([]);
  const [sections, setSections] = useState<WritingOutlineSection[]>([]);
  const [supportedTopicTypes, setSupportedTopicTypes] = useState<TopicTypeChoice[]>(
    [],
  );
  const [unsupportedFutureType, setUnsupportedFutureType] =
    useState<FutureTopicType | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [pendingLabel, setPendingLabel] = useState("");
  const ignoreActiveResumeRef = useRef(false);

  useEffect(() => {
    let isMounted = true;

    async function loadActiveEssay() {
      try {
        const response = await getActiveClassroomWritingCastleEssay(studentId);
        if (!isMounted || ignoreActiveResumeRef.current || !response.essay) {
          return;
        }
        const activeEssay = response.essay;
        setEssay(activeEssay);
        setTopicText(activeEssay.title);
        const nextSuggestedFocus =
          activeEssay.outline.topic_analysis.suggested_focus ?? "";
        setSuggestedFocus(nextSuggestedFocus);
        setFocus(
          activeEssay.outline.child_topic_focus.text || nextSuggestedFocus,
        );
        setAnswers(answersFromEssay(activeEssay));
        setCards(activeEssay.material_card.cards);
        setSections(activeEssay.outline.sections);
        const nextStep = stepFromEssay(activeEssay);
        if (nextStep === "scaffold_selection") {
          setSupportedTopicTypes(
            response.supported_topic_types?.length
              ? response.supported_topic_types
              : DEFAULT_SUPPORTED_TOPIC_TYPES,
          );
        }
        setUnsupportedFutureType(
          response.unsupported_future_type ??
            activeEssay.outline.scaffold?.unsupported_future_type ??
            null,
        );
        setStep(nextStep);
      } catch {
        if (isMounted && !ignoreActiveResumeRef.current) {
          setError("");
        }
      }
    }

    void loadActiveEssay();

    return () => {
      isMounted = false;
    };
  }, [studentId]);

  async function run<T>(
    label: string,
    action: () => Promise<T>,
  ): Promise<T | null> {
    setPendingLabel(label);
    setError("");
    try {
      return await action();
    } catch {
      setError("这一步没有保存成功，可以重试，也可以先继续写。");
      return null;
    } finally {
      setPendingLabel("");
    }
  }

  async function start() {
    ignoreActiveResumeRef.current = true;
    const started = await run("正在准备作文类型...", async () =>
      createClassroomWritingCastleEssay(studentId, {
        topic_text: topicText,
      }),
    );

    if (started) {
      setEssay(started.essay);
      setSupportedTopicTypes(
        started.supported_topic_types.length > 0
          ? started.supported_topic_types
          : DEFAULT_SUPPORTED_TOPIC_TYPES,
      );
      setUnsupportedFutureType(started.unsupported_future_type ?? null);
      setSuggestedFocus("");
      setFocus("");
      setAnswers(answersFromEssay(started.essay));
      setCards(started.essay.material_card.cards);
      setSections(started.essay.outline.sections);
      setStep("scaffold_selection");
    }
  }

  async function selectScaffold(topicType: TopicType) {
    if (!essay) {
      return;
    }

    const started = await run("正在看题目...", async () => {
      const saved = await selectWritingCastleScaffold(essay.id, {
        topic_type: topicType,
        override_reason: "manual_choice",
        ...(unsupportedFutureType
          ? { unsupported_future_type: unsupportedFutureType }
          : {}),
      });
      const analyzed = await generateTopicAnalysis(saved.essay.id);
      return analyzed.essay;
    });

    if (started) {
      const nextSuggestedFocus =
        started.outline.topic_analysis.suggested_focus ?? "";
      setEssay(started);
      setSuggestedFocus(nextSuggestedFocus);
      setFocus(nextSuggestedFocus);
      setStep("topic_analysis");
    }
  }

  async function continueFromTopic(skipped: boolean) {
    if (!essay) {
      return;
    }

    const saved = await run("正在准备选材问题...", async () => {
      await saveTopicFocus(essay.id, {
        text: skipped ? "" : focus,
        adopted_from_ai:
          !skipped &&
          suggestedFocus.trim().length > 0 &&
          focus === suggestedFocus,
        skipped,
      });
      const generated = await generateMaterialQuestions(essay.id);
      return generated.essay;
    });

    if (saved) {
      setEssay(saved);
      setAnswers(
        saved.material_card.questions.map((question) => ({
          id: `answer-${question.id}`,
          question_id: question.id,
          text: "",
          skipped: false,
        })),
      );
      setStep("questions");
    }
  }

  async function continueFromQuestions(direct = false) {
    if (!essay) {
      return;
    }
    if (direct) {
      const saved = await run("正在保存素材回答...", async () =>
        saveMaterialAnswers(essay.id, { answers }),
      );
      if (!saved) {
        return;
      }
      setEssay(saved.essay);
      setStep("draft");
      return;
    }

    const saved = await run("正在整理素材卡...", async () => {
      await saveMaterialAnswers(essay.id, { answers });
      const generated = await generateMaterialCards(essay.id);
      return generated.essay;
    });

    if (saved) {
      setEssay(saved);
      setCards(saved.material_card.cards);
      setStep("cards");
    }
  }

  async function continueFromCards(direct = false) {
    if (!essay) {
      return;
    }
    if (direct) {
      const saved = await run("正在保存素材卡...", async () =>
        saveMaterialCards(essay.id, { cards }),
      );
      if (!saved) {
        return;
      }
      setEssay(saved.essay);
      setStep("draft");
      return;
    }

    const saved = await run("正在搭提纲...", async () => {
      await saveMaterialCards(essay.id, { cards });
      const generated = await generateOutline(essay.id);
      return generated.essay;
    });

    if (saved) {
      setEssay(saved);
      setSections(saved.outline.sections);
      setStep("outline");
    }
  }

  async function continueFromOutline(direct = false) {
    if (!essay) {
      return;
    }
    const saved = await run("正在保存提纲...", async () =>
      saveOutline(essay.id, { sections, skipped: direct }),
    );
    if (!saved) {
      return;
    }
    setEssay(saved.essay);
    setSections(saved.essay.outline.sections);
    setStep("draft");
  }

  async function submitDraft() {
    if (!essay) {
      return;
    }

    const result = await run("AI 教练正在读你的初稿", async () =>
      submitPrewritingFirstDraft(essay.id, { draft }),
    );

    if (result) {
      onFeedback(result);
      setStep("feedback");
    }
  }

  if (step === "topic_entry") {
    return (
      <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
        <label className="block font-semibold">
          老师作文题目
          <textarea
            className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
            value={topicText}
            onChange={(event) => {
              ignoreActiveResumeRef.current = true;
              setTopicText(event.target.value);
            }}
            placeholder="把老师布置的题目写在这里"
          />
        </label>
        <button
          className="mt-4 rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white disabled:opacity-60"
          type="button"
          disabled={!topicText.trim() || Boolean(pendingLabel)}
          onClick={start}
        >
          开始审题
        </button>
        <WizardStatus pendingLabel={pendingLabel} error={error} />
      </section>
    );
  }

  if (!essay) {
    return null;
  }

  const slotLabels = Object.fromEntries(
    essay.outline.scaffold?.material_slots.map((slot) => [
      slot.id,
      slot.label,
    ]) ?? [],
  );
  const sectionLabels = Object.fromEntries(
    essay.outline.scaffold?.outline_sections.map((section) => [
      section.id,
      section.label ?? section.heading,
    ]) ?? [],
  );

  return (
    <>
      {step === "scaffold_selection" ? (
        <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
          <h2 className="text-xl font-bold">选择作文类型</h2>
          {unsupportedFutureType ? (
            <p className="mt-3 text-sm font-semibold text-[var(--wen-muted)]">
              这类题目我们还在学习中，可以先选最接近的一种写法，AI 教练会陪你一步一步写。
            </p>
          ) : null}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {supportedTopicTypes.map((choice) => (
              <button
                key={choice.topic_type}
                className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-4 text-left font-semibold disabled:opacity-60"
                type="button"
                disabled={Boolean(pendingLabel)}
                onClick={() => selectScaffold(choice.topic_type)}
              >
                {choice.display_name_child}
              </button>
            ))}
          </div>
        </section>
      ) : null}
      {step === "topic_analysis" ? (
        <TopicAnalysisStep
          cards={essay.outline.topic_analysis.cards}
          focus={focus}
          onFocusChange={setFocus}
          onContinue={() => continueFromTopic(false)}
          onSkip={() => continueFromTopic(true)}
        />
      ) : null}
      {step === "questions" ? (
        <MaterialQuestionsStep
          questions={essay.material_card.questions}
          answers={answers}
          onAnswersChange={setAnswers}
          onContinue={() => continueFromQuestions(false)}
          onDirectWrite={() => continueFromQuestions(true)}
        />
      ) : null}
      {step === "cards" ? (
        <MaterialCardsStep
          cards={cards}
          slotLabels={slotLabels}
          onCardsChange={setCards}
          onContinue={() => continueFromCards(false)}
          onDirectWrite={() => continueFromCards(true)}
        />
      ) : null}
      {step === "outline" ? (
        <OutlineStep
          sections={sections}
          sectionLabels={sectionLabels}
          onSectionsChange={setSections}
          onContinue={() => continueFromOutline(false)}
          onDirectWrite={() => continueFromOutline(true)}
        />
      ) : null}
      {step === "draft" ? (
        <FirstDraftStep
          cards={cards}
          sections={sections}
          draft={draft}
          onDraftChange={setDraft}
          onSubmit={submitDraft}
          isPending={Boolean(pendingLabel)}
        />
      ) : null}
      <WizardStatus pendingLabel={pendingLabel} error={error} />
    </>
  );
}

function WizardStatus({
  pendingLabel,
  error,
}: {
  pendingLabel: string;
  error: string;
}) {
  return (
    <>
      {pendingLabel ? (
        <p role="status" className="mt-3 font-semibold">
          {pendingLabel}
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-[var(--wen-orange)] bg-white p-4 font-semibold"
        >
          {error}
        </p>
      ) : null}
    </>
  );
}
