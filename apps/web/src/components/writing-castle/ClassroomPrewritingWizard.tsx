"use client";

import { useEffect, useRef, useState } from "react";
import { AiWaitingStatus } from "../AiWaitingStatus";
import {
  createMaterialCardsJob,
  createClassroomWritingCastleEssay,
  createOutlineJob,
  fetchEssayFeedbackResult,
  generateMaterialCards,
  generateMaterialQuestions,
  generateOutline,
  generateTopicAnalysis,
  getActiveClassroomWritingCastleEssay,
  getPrewritingJob,
  openPrewritingJobEvents,
  saveMaterialAnswers,
  saveMaterialCards,
  saveOutline,
  saveTopicFocus,
  selectWritingCastleScaffold,
  streamPrewritingFirstDraftFeedback,
  submitPrewritingFirstDraft,
  type EssayResponse,
  type PrewritingJobResponse,
} from "../../lib/api";
import { reduceStreamEvent, type StreamReducerState } from "../../lib/sse";
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

const LOADING_STAGE_MS = 2200;
const PREWRITING_JOB_POLL_MS = 120;
const PREWRITING_JOB_RESULT_TIMEOUT_MS = 5000;

const LOADING_COPY = {
  start_classroom: ["正在准备作文类型……"],
  topic_analysis: [
    "正在读题目……",
    "正在找这类作文的重点……",
    "正在整理审题提示……",
  ],
  material_questions: [
    "正在根据题型准备问题……",
    "正在提醒你从哪里找素材……",
    "马上就能开始想素材了……",
  ],
  material_cards: [
    "正在整理你的回答……",
    "正在把素材放进合适卡片……",
    "正在检查有没有替你编内容……",
  ],
  outline: [
    "正在搭提纲……",
    "正在按题型安排段落……",
    "正在检查提纲有没有素材来源……",
  ],
  first_draft_feedback: [
    "AI 教练正在读你的初稿……",
    "正在先找写得好的地方……",
    "正在准备一个小修改任务……",
  ],
  save_answers: ["正在保存素材回答……"],
  save_cards: ["正在保存素材卡……"],
  save_outline: ["正在保存提纲……"],
} as const;

type LoadingKey = keyof typeof LOADING_COPY;

function loadingMessages(key: LoadingKey): readonly string[] {
  return LOADING_COPY[key];
}

function isEssayFeedbackStreamingEnabled() {
  return process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED === "true";
}

function isPrewritingProgressJobsEnabled() {
  return process.env.NEXT_PUBLIC_PREWRITING_PROGRESS_JOBS_ENABLED === "true";
}

function wait(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function createClientSubmissionId() {
  return `client-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function prewritingJobMessage(
  loadingKey: "material_cards" | "outline",
  job: Pick<PrewritingJobResponse, "stage" | "status">,
): string {
  const labels = {
    material_cards: {
      queued: "素材卡排队中……",
      primary_started: "AI 正在整理素材卡……",
      primary_slow: "素材卡生成有点慢，正在继续等……",
      fallback_started: "正在切换备用方式整理素材卡……",
      completed: "素材卡整理完成，正在打开结果……",
      failed: "素材卡暂时没有整理成功。",
    },
    outline: {
      queued: "提纲排队中……",
      primary_started: "AI 正在搭提纲……",
      primary_slow: "提纲生成有点慢，正在继续等……",
      fallback_started: "正在切换备用方式搭提纲……",
      completed: "提纲完成，正在打开结果……",
      failed: "提纲暂时没有生成成功。",
    },
  } as const;
  const key = job.status === "completed" || job.status === "failed"
    ? job.status
    : job.stage;
  return labels[loadingKey][key as keyof (typeof labels)[typeof loadingKey]] ??
    loadingMessages(loadingKey)[0];
}

function prewritingJobFromEvent(event: MessageEvent): PrewritingJobResponse {
  const data = JSON.parse(event.data) as Partial<PrewritingJobResponse>;
  return {
    schema_version: data.schema_version ?? "v0.6e.1",
    job_id: data.job_id ?? "",
    task_name: data.task_name ?? "",
    status: data.status ?? "",
    stage: data.stage ?? "",
    seq: data.seq ?? 0,
    result_ref_type: data.result_ref_type ?? "",
    result_ref_id: data.result_ref_id ?? null,
    error_code: data.error_code ?? "",
    error_message: data.error_message ?? "",
  };
}

function emptyFeedback(): EssayResponse["feedback"] {
  return {
    strengths: [],
    improvements: [],
    problem_monsters: [],
    sentence_notes: [],
    revision_tasks: [],
  };
}

function previewFeedbackFromStream(
  essayId: string,
  streamState: StreamReducerState,
): EssayResponse {
  const sections = streamState.sections;
  return {
    essay: { id: essayId },
    first_draft: {
      id: "",
      essay_id: essayId,
      version_label: "first_draft",
      reaction: null,
    },
    feedback: {
      ...emptyFeedback(),
      strengths: sections.strengths ?? [],
      improvements: sections.improvements ?? [],
      problem_monsters: sections.problem_monsters ?? [],
      sentence_notes: sections.sentence_notes ?? [],
      revision_tasks: (sections.revision_tasks ?? []).map((instruction) => ({
        instruction,
        target: "",
      })),
    },
  };
}

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

function stepFromInitialEssay(essay: WritingCastleEssay): Step {
  if (
    essay.outline.scaffold &&
    essay.outline.topic_analysis.status !== "generated"
  ) {
    return "topic_analysis";
  }
  return stepFromEssay(essay);
}

export function ClassroomPrewritingWizard({
  studentId,
  onFeedback,
  feedbackEpoch = 0,
  initialEssay = null,
  skipActiveResume = false,
  onEssayChange,
}: {
  studentId: string;
  onFeedback: (result: EssayResponse, feedbackEpoch?: number) => void;
  feedbackEpoch?: number;
  initialEssay?: WritingCastleEssay | null;
  skipActiveResume?: boolean;
  onEssayChange?: (essay: WritingCastleEssay) => void;
}) {
  const [step, setStep] = useState<Step>(() =>
    initialEssay ? stepFromInitialEssay(initialEssay) : "topic_entry",
  );
  const [topicText, setTopicText] = useState(() => initialEssay?.title ?? "");
  const [essay, setEssay] = useState<WritingCastleEssay | null>(
    () => initialEssay,
  );
  const [focus, setFocus] = useState(() => {
    if (!initialEssay) {
      return "";
    }
    const suggested = initialEssay.outline.topic_analysis.suggested_focus ?? "";
    return initialEssay.outline.child_topic_focus.text || suggested;
  });
  const [suggestedFocus, setSuggestedFocus] = useState(
    () => initialEssay?.outline.topic_analysis.suggested_focus ?? "",
  );
  const [answers, setAnswers] = useState<MaterialAnswer[]>(() =>
    initialEssay ? answersFromEssay(initialEssay) : [],
  );
  const [cards, setCards] = useState<MaterialCardSlot[]>(
    () => initialEssay?.material_card.cards ?? [],
  );
  const [sections, setSections] = useState<WritingOutlineSection[]>(
    () => initialEssay?.outline.sections ?? [],
  );
  const [supportedTopicTypes, setSupportedTopicTypes] = useState<TopicTypeChoice[]>(
    [],
  );
  const [unsupportedFutureType, setUnsupportedFutureType] =
    useState<FutureTopicType | null>(
      () => initialEssay?.outline.scaffold?.unsupported_future_type ?? null,
    );
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [pendingMessages, setPendingMessages] = useState<readonly string[]>([]);
  const [pendingMessageIndex, setPendingMessageIndex] = useState(0);
  const [pendingServerMessage, setPendingServerMessage] = useState<string | null>(
    null,
  );
  const [draftFeedbackPreview, setDraftFeedbackPreview] = useState<
    EssayResponse["feedback"] | null
  >(null);
  const ignoreActiveResumeRef = useRef(false);
  const mountedRef = useRef(true);
  const prewritingJobEventSourceRef = useRef<EventSource | null>(null);
  const prewritingJobCancelRef = useRef<(() => void) | null>(null);
  const draftFeedbackAbortControllerRef = useRef<AbortController | null>(null);
  const pendingLabel = pendingMessages[pendingMessageIndex] ?? "";

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      prewritingJobCancelRef.current?.();
      prewritingJobCancelRef.current = null;
      prewritingJobEventSourceRef.current?.close();
      prewritingJobEventSourceRef.current = null;
      draftFeedbackAbortControllerRef.current?.abort();
      draftFeedbackAbortControllerRef.current = null;
    };
  }, []);

  function applyActiveEssayState(response: {
    essay: WritingCastleEssay;
    supported_topic_types?: TopicTypeChoice[];
    unsupported_future_type?: FutureTopicType | null;
  }) {
    const activeEssay = response.essay;
    setEssay(activeEssay);
    setTopicText(activeEssay.title);
    const nextSuggestedFocus =
      activeEssay.outline.topic_analysis.suggested_focus ?? "";
    setSuggestedFocus(nextSuggestedFocus);
    setFocus(activeEssay.outline.child_topic_focus.text || nextSuggestedFocus);
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
  }

  useEffect(() => {
    let isMounted = true;

    async function loadActiveEssay() {
      if (skipActiveResume) {
        return;
      }
      try {
        const response = await getActiveClassroomWritingCastleEssay(studentId);
        if (!isMounted || ignoreActiveResumeRef.current || !response.essay) {
          return;
        }
        applyActiveEssayState(response);
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
  }, [studentId, skipActiveResume]);

  useEffect(() => {
    if (!initialEssay) {
      return;
    }

    let isMounted = true;
    ignoreActiveResumeRef.current = true;
    async function startInitialEssayAnalysis() {
      if (
        !initialEssay.outline.scaffold ||
        initialEssay.outline.topic_analysis.status === "generated"
      ) {
        return;
      }

      setPendingMessages([...loadingMessages("topic_analysis")]);
      setPendingMessageIndex(0);
      setError("");
      try {
        const analyzed = await generateTopicAnalysis(initialEssay.id);
        onEssayChange?.(analyzed.essay);
        if (!isMounted) {
          return;
        }
        const nextSuggestedFocus =
          analyzed.essay.outline.topic_analysis.suggested_focus ?? "";
        setEssay(analyzed.essay);
        setSuggestedFocus(nextSuggestedFocus);
        setFocus(nextSuggestedFocus);
        setAnswers(answersFromEssay(analyzed.essay));
        setCards(analyzed.essay.material_card.cards);
        setSections(analyzed.essay.outline.sections);
        setStep("topic_analysis");
      } catch {
        if (isMounted) {
          setError("这一步没有保存成功，可以重试，也可以先继续写。");
        }
      } finally {
        if (isMounted) {
          setPendingMessages([]);
          setPendingMessageIndex(0);
        }
      }
    }

    void startInitialEssayAnalysis();

    return () => {
      isMounted = false;
    };
  }, [initialEssay, onEssayChange]);

  useEffect(() => {
    if (pendingMessages.length <= 1) {
      return;
    }
    const timer = window.setInterval(() => {
      setPendingMessageIndex((index) => {
        if (index >= pendingMessages.length - 1) {
          window.clearInterval(timer);
          return index;
        }
        return index + 1;
      });
    }, LOADING_STAGE_MS);
    return () => window.clearInterval(timer);
  }, [pendingMessages]);

  async function run<T>(
    loadingKey: LoadingKey,
    action: () => Promise<T>,
    recover?: () => Promise<T | null>,
  ): Promise<T | null> {
    setPendingMessages([...loadingMessages(loadingKey)]);
    setPendingMessageIndex(0);
    setPendingServerMessage(null);
    setError("");
    try {
      return await action();
    } catch {
      if (recover) {
        try {
          const recovered = await recover();
          if (recovered) {
            return recovered;
          }
        } catch {
          // Keep the original user-facing retry path when recovery cannot read progress.
        }
      }
      if (mountedRef.current) {
        setError("这一步没有保存成功，可以重试，也可以先继续写。");
      }
      return null;
    } finally {
      if (mountedRef.current) {
        setPendingMessages([]);
        setPendingMessageIndex(0);
        setPendingServerMessage(null);
      }
    }
  }

  async function waitForPrewritingJobEssay(
    loadingKey: "material_cards" | "outline",
    expectedEssayId: string,
    jobId: string,
    isCanonicalStateReady: (activeEssay: WritingCastleEssay) => boolean,
  ): Promise<WritingCastleEssay> {
    try {
      await waitForPrewritingJobEventCompletion(loadingKey, jobId);
    } catch {
      return waitForPrewritingJobEssayByPolling(
        loadingKey,
        expectedEssayId,
        jobId,
        isCanonicalStateReady,
      );
    }
    return fetchCompletedPrewritingJobEssay(
      expectedEssayId,
      isCanonicalStateReady,
    );
  }

  async function waitForPrewritingJobEventCompletion(
    loadingKey: "material_cards" | "outline",
    jobId: string,
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const source = openPrewritingJobEvents(jobId);
      prewritingJobEventSourceRef.current?.close();
      prewritingJobEventSourceRef.current = source;
      let settled = false;
      let cancel: () => void;

      const settle = (callback: () => void) => {
        if (settled) {
          return;
        }
        settled = true;
        source.close();
        if (prewritingJobEventSourceRef.current === source) {
          prewritingJobEventSourceRef.current = null;
        }
        if (prewritingJobCancelRef.current === cancel) {
          prewritingJobCancelRef.current = null;
        }
        callback();
      };
      cancel = () => {
        settle(() => reject(new Error("prewriting job listener unmounted")));
      };
      prewritingJobCancelRef.current = cancel;
      const handleEvent = (event: Event) => {
        if (!mountedRef.current) {
          settle(() => reject(new Error("prewriting job listener unmounted")));
          return;
        }
        try {
          const job = prewritingJobFromEvent(event as MessageEvent);
          setPendingServerMessage(prewritingJobMessage(loadingKey, job));
          if (job.status === "failed") {
            settle(() => reject(new Error(job.error_message || "prewriting job failed")));
            return;
          }
          if (job.status === "completed") {
            settle(resolve);
          }
        } catch (error) {
          settle(() => reject(error));
        }
      };

      source.addEventListener("progress", handleEvent);
      source.addEventListener("completed", handleEvent);
      source.addEventListener("failed", handleEvent);
      source.onerror = () => {
        settle(() => reject(new Error("prewriting job event stream failed")));
      };
    });
  }

  async function waitForPrewritingJobEssayByPolling(
    loadingKey: "material_cards" | "outline",
    expectedEssayId: string,
    jobId: string,
    isCanonicalStateReady: (activeEssay: WritingCastleEssay) => boolean,
  ): Promise<WritingCastleEssay> {
    await wait(PREWRITING_JOB_POLL_MS);
    while (true) {
      if (!mountedRef.current) {
        throw new Error("prewriting job listener unmounted");
      }
      const job = await getPrewritingJob(jobId);
      if (!mountedRef.current) {
        throw new Error("prewriting job listener unmounted");
      }
      setPendingServerMessage(prewritingJobMessage(loadingKey, job));
      if (job.status === "failed") {
        throw new Error(job.error_message || "prewriting job failed");
      }
      if (job.status === "completed") {
        return fetchCompletedPrewritingJobEssay(
          expectedEssayId,
          isCanonicalStateReady,
        );
      }
      await wait(PREWRITING_JOB_POLL_MS);
    }
  }

  async function fetchCompletedPrewritingJobEssay(
    expectedEssayId: string,
    isCanonicalStateReady: (activeEssay: WritingCastleEssay) => boolean,
  ): Promise<WritingCastleEssay> {
    const startedAt = Date.now();
    while (true) {
      if (!mountedRef.current) {
        throw new Error("prewriting job listener unmounted");
      }
      const response = await getActiveClassroomWritingCastleEssay(studentId);
      if (
        response.essay &&
        response.essay.id === expectedEssayId &&
        isCanonicalStateReady(response.essay)
      ) {
        return response.essay;
      }
      if (Date.now() - startedAt >= PREWRITING_JOB_RESULT_TIMEOUT_MS) {
        throw new Error("completed prewriting job did not return essay state");
      }
      await wait(PREWRITING_JOB_POLL_MS);
    }
  }

  function hasCanonicalMaterialCards(activeEssay: WritingCastleEssay): boolean {
    return (
      activeEssay.material_card.cards.length > 0 ||
      activeEssay.material_card.step_state.cards_status === "generated"
    );
  }

  function hasCanonicalOutline(activeEssay: WritingCastleEssay): boolean {
    return (
      activeEssay.outline.sections.length > 0 ||
      activeEssay.outline.step_state.outline_status === "generated"
    );
  }

  async function recoverActiveEssay(
    expectedEssayId: string,
    isRecovered: (activeEssay: WritingCastleEssay) => boolean,
  ): Promise<WritingCastleEssay | null> {
    const response = await getActiveClassroomWritingCastleEssay(studentId);
    if (!response.essay || response.essay.id !== expectedEssayId) {
      return null;
    }
    if (!isRecovered(response.essay)) {
      return null;
    }
    applyActiveEssayState(response);
    return response.essay;
  }

  function materialAnswersMatch(
    activeEssay: WritingCastleEssay,
    expectedAnswers: MaterialAnswer[],
  ): boolean {
    const activeByQuestionId = new Map(
      activeEssay.material_card.answers.map((answer) => [
        answer.question_id,
        answer,
      ]),
    );
    return expectedAnswers.every((expectedAnswer) => {
      const activeAnswer = activeByQuestionId.get(expectedAnswer.question_id);
      if (!activeAnswer && expectedAnswer.text.trim().length === 0) {
        return true;
      }
      return (
        activeAnswer &&
        activeAnswer.text === expectedAnswer.text &&
        activeAnswer.skipped === expectedAnswer.skipped
      );
    });
  }

  async function saveMaterialAnswersWithRecovery(
    essayId: string,
    nextAnswers: MaterialAnswer[],
  ): Promise<void> {
    try {
      await saveMaterialAnswers(essayId, { answers: nextAnswers });
    } catch (error) {
      const recovered = await recoverActiveEssay(essayId, (activeEssay) =>
        materialAnswersMatch(activeEssay, nextAnswers),
      );
      if (!recovered) {
        throw error;
      }
    }
  }

  async function start() {
    ignoreActiveResumeRef.current = true;
    const started = await run("start_classroom", async () =>
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

    const started = await run("topic_analysis", async () => {
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

    const saved = await run("material_questions", async () => {
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
      const saved = await run("save_answers", async () =>
        saveMaterialAnswers(essay.id, { answers }),
      );
      if (!saved) {
        return;
      }
      setEssay(saved.essay);
      setStep("draft");
      return;
    }

    const saved = await run("material_cards", async () => {
      await saveMaterialAnswersWithRecovery(essay.id, answers);
      if (isPrewritingProgressJobsEnabled()) {
        const job = await createMaterialCardsJob(essay.id, {
          idempotency_key: globalThis.crypto.randomUUID(),
        });
        setPendingServerMessage(prewritingJobMessage("material_cards", job));
        return waitForPrewritingJobEssay(
          "material_cards",
          essay.id,
          job.job_id,
          hasCanonicalMaterialCards,
        );
      }
      const generated = await generateMaterialCards(essay.id);
      return generated.essay;
    }, () =>
      recoverActiveEssay(
        essay.id,
        (activeEssay) => activeEssay.material_card.cards.length > 0,
      ),
    );

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
      const saved = await run("save_cards", async () =>
        saveMaterialCards(essay.id, { cards }),
      );
      if (!saved) {
        return;
      }
      setEssay(saved.essay);
      setStep("draft");
      return;
    }

    const saved = await run("outline", async () => {
      await saveMaterialCards(essay.id, { cards });
      if (isPrewritingProgressJobsEnabled()) {
        const job = await createOutlineJob(essay.id, {
          idempotency_key: globalThis.crypto.randomUUID(),
        });
        setPendingServerMessage(prewritingJobMessage("outline", job));
        return waitForPrewritingJobEssay(
          "outline",
          essay.id,
          job.job_id,
          hasCanonicalOutline,
        );
      }
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
    const saved = await run("save_outline", async () =>
      saveOutline(essay.id, { sections, skipped: direct }),
    );
    if (!saved) {
      return;
    }
    setEssay(saved.essay);
    setSections(saved.essay.outline.sections);
    setStep("draft");
  }

  function enterDraftWithoutScaffold() {
    setError("");
    setPendingMessages([]);
    setPendingMessageIndex(0);
    setPendingServerMessage(null);
    setStep("draft");
  }

  function returnToTopicEntry() {
    ignoreActiveResumeRef.current = true;
    setEssay(null);
    setTopicText("");
    setFocus("");
    setSuggestedFocus("");
    setAnswers([]);
    setCards([]);
    setSections([]);
    setSupportedTopicTypes([]);
    setUnsupportedFutureType(null);
    setDraft("");
    setError("");
    setPendingMessages([]);
    setPendingMessageIndex(0);
    setPendingServerMessage(null);
    setStep("topic_entry");
  }

  async function submitDraft() {
    if (!essay) {
      return;
    }

    setDraftFeedbackPreview(null);
    draftFeedbackAbortControllerRef.current?.abort();
    const abortController = new AbortController();
    draftFeedbackAbortControllerRef.current = abortController;
    const isCurrentDraftFeedbackRequest = () =>
      mountedRef.current && !abortController.signal.aborted;
    const clientSubmissionId = createClientSubmissionId();
    const requestFeedbackEpoch = feedbackEpoch;
    const result = await run("first_draft_feedback", async () => {
      if (!isEssayFeedbackStreamingEnabled()) {
        return submitPrewritingFirstDraft(essay.id, {
          draft,
          client_submission_id: clientSubmissionId,
        });
      }

      let streamState: StreamReducerState | undefined;
      let sawPreview = false;
      try {
        await streamPrewritingFirstDraftFeedback(
          essay.id,
          { draft, client_submission_id: clientSubmissionId },
          (frame) => {
            if (!isCurrentDraftFeedbackRequest()) {
              return;
            }
            streamState = reduceStreamEvent(streamState, frame);
            if (frame.event === "feedback_section_preview" && streamState) {
              sawPreview = true;
              setDraftFeedbackPreview(
                previewFeedbackFromStream(essay.id, streamState).feedback,
              );
            }
          },
          { signal: abortController.signal },
        );
      } catch (error) {
        if (!isCurrentDraftFeedbackRequest()) {
          throw error;
        }
        if (sawPreview) {
          throw error;
        }
        return submitPrewritingFirstDraft(essay.id, {
          draft,
          client_submission_id: clientSubmissionId,
        });
      }
      if (!isCurrentDraftFeedbackRequest()) {
        throw new Error("stale first draft feedback stream");
      }
      if (!streamState?.fetchUrl) {
        throw new Error("stream completed without a feedback result URL");
      }
      return fetchEssayFeedbackResult(streamState.fetchUrl);
    });

    if (draftFeedbackAbortControllerRef.current === abortController) {
      draftFeedbackAbortControllerRef.current = null;
    }

    if (result && mountedRef.current) {
      onFeedback(result, requestFeedbackEpoch);
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
        <WizardStatus
          pendingLabel={pendingLabel}
          pendingServerMessage={pendingServerMessage}
          error={error}
        />
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
          {unsupportedFutureType ? (
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white disabled:opacity-60"
                type="button"
                disabled={Boolean(pendingLabel)}
                onClick={enterDraftWithoutScaffold}
              >
                直接写初稿
              </button>
              <button
                className="rounded-lg border border-[var(--wen-border)] bg-white px-4 py-2 font-semibold disabled:opacity-60"
                type="button"
                disabled={Boolean(pendingLabel)}
                onClick={returnToTopicEntry}
              >
                重新输入题目
              </button>
            </div>
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
        <>
          <FirstDraftStep
            cards={cards}
            slotLabels={slotLabels}
            sections={sections}
            draft={draft}
            onDraftChange={setDraft}
            onSubmit={submitDraft}
            isPending={Boolean(pendingLabel)}
          />
          {draftFeedbackPreview ? (
            <DraftFeedbackPreview feedback={draftFeedbackPreview} />
          ) : null}
        </>
      ) : null}
      <WizardStatus
        pendingLabel={pendingLabel}
        pendingServerMessage={pendingServerMessage}
        error={error}
      />
    </>
  );
}

function WizardStatus({
  pendingLabel,
  pendingServerMessage,
  error,
}: {
  pendingLabel: string;
  pendingServerMessage: string | null;
  error: string;
}) {
  return (
    <>
      {pendingLabel ? (
        <div className="mt-3">
          <AiWaitingStatus
            messages={[pendingLabel]}
            serverMessage={pendingServerMessage ?? pendingLabel}
          />
        </div>
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

function DraftFeedbackPreview({
  feedback,
}: {
  feedback: EssayResponse["feedback"];
}) {
  const sections = [
    { title: "写得好的地方", items: feedback.strengths },
    { title: "可以改进的地方", items: feedback.improvements },
    { title: "句子小提示", items: feedback.sentence_notes },
    {
      title: "修改小任务",
      items: feedback.revision_tasks.map((task) => task.instruction),
    },
  ].filter((section) => section.items.length > 0);

  if (sections.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="初稿点评预览"
      className="mt-4 space-y-3 rounded-lg border border-[var(--wen-border)] bg-white p-4"
    >
      {sections.map((section) => (
        <div key={section.title}>
          <h3 className="font-semibold">{section.title}</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {section.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
