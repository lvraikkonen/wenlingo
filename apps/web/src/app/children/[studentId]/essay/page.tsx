"use client";

import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Archive, CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { AssessmentRecommendationCard } from "../../../../components/AssessmentRecommendationCard";
import { FamilyTopbar } from "../../../../components/FamilyTopbar";
import { FeedbackReaction } from "../../../../components/FeedbackReaction";
import { SettlementPanel } from "../../../../components/SettlementPanel";
import { AiTopicIdeaFlow } from "../../../../components/writing-castle/AiTopicIdeaFlow";
import { ClassroomPrewritingWizard } from "../../../../components/writing-castle/ClassroomPrewritingWizard";
import { EssayArchiveDrawer } from "../../../../components/writing-castle/EssayArchiveDrawer";
import {
  WritingCastleModeShell,
  type WritingCastleMode,
} from "../../../../components/writing-castle/WritingCastleModeShell";
import {
  createEssay,
  fetchEssayFeedbackResult,
  fetchEssayArchiveDetail,
  streamEssayFeedback,
  submitEssayRevision,
  type EssayResponse,
  type EssayRevisionResponse,
  type Settlement,
} from "../../../../lib/api";
import { reduceStreamEvent, type StreamReducerState } from "../../../../lib/sse";
import type { WritingCastleEssay } from "../../../../lib/types";
import { useAssessmentRecommendation } from "../../../../lib/useAssessmentRecommendation";

export default function EssayPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);

  return <EssayPageContent key={studentId} studentId={studentId} />;
}

function getCurrentTimeMs() {
  return Date.now();
}

function createClientSubmissionId() {
  return `client-${getCurrentTimeMs()}-${Math.random().toString(36).slice(2)}`;
}

function isEssayFeedbackStreamingEnabled() {
  return process.env.NEXT_PUBLIC_ESSAY_FEEDBACK_STREAMING_ENABLED === "true";
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
  streamState: StreamReducerState,
): EssayResponse["feedback"] {
  const sections = streamState.sections;
  return {
    ...emptyFeedback(),
    strengths: sections.strengths ?? [],
    improvements: sections.improvements ?? [],
    problem_monsters: sections.problem_monsters ?? [],
    sentence_notes: sections.sentence_notes ?? [],
    revision_tasks: (sections.revision_tasks ?? []).map((instruction) => ({
      instruction,
      target: "",
    })),
  };
}

function EssayPageContent({ studentId }: { studentId: string }) {
  const activeStudentId = useRef<string | null>(studentId);
  const archiveSelectionRequestId = useRef(0);
  const feedbackRequestId = useRef(0);
  const feedbackAbortControllerRef = useRef<AbortController | null>(null);
  const prewritingFeedbackEpochRef = useRef(0);
  const revisionRequestId = useRef(0);
  const isRevisionSubmitting = useRef(false);
  const revisionSubmitKeyRef = useRef<string | null>(null);
  const pendingRevisionPayload = useRef<{
    content: string;
    completedTasks: string[];
    skippedTasks: string[];
  } | null>(null);
  const loadedDirectInput = useRef({ title: "", draft: "" });
  const loadedRevision = useRef("");
  const {
    shouldShowAssessmentRecommendation,
    dismissAssessmentRecommendation,
  } = useAssessmentRecommendation(studentId);
  const [title, setTitle] = useState("");
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<WritingCastleMode>("classroom");
  const [prewritingFeedbackEpoch, setPrewritingFeedbackEpoch] = useState(0);
  const [aiTopicEssay, setAiTopicEssay] = useState<WritingCastleEssay | null>(
    null,
  );
  const [revision, setRevision] = useState("");
  const [essayId, setEssayId] = useState<string | null>(null);
  const [firstDraftId, setFirstDraftId] = useState<string | null>(null);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [baseVersionId, setBaseVersionId] = useState<string | null>(null);
  const [currentRoundIndex, setCurrentRoundIndex] = useState<number | null>(null);
  const [revisionSubmitKey, setRevisionSubmitKey] = useState<string | null>(null);
  const [hasUnsubmittedRevisionInput, setHasUnsubmittedRevisionInput] =
    useState(false);
  const [hasUnsubmittedDirectInput, setHasUnsubmittedDirectInput] =
    useState(false);
  const [firstDraftReaction, setFirstDraftReaction] = useState<
    EssayResponse["first_draft"]["reaction"]
  >(null);
  const [revisionResultId, setRevisionResultId] = useState<string | null>(null);
  const [revisionResultReaction, setRevisionResultReaction] = useState<
    EssayRevisionResponse["revision"]["reaction"]
  >(null);
  const [feedback, setFeedback] = useState<null | EssayResponse["feedback"]>(
    null,
  );
  const [comparison, setComparison] = useState<
    null | EssayRevisionResponse["comparison"]
  >(null);
  const [settlement, setSettlement] = useState<Settlement | null>(null);
  const [selectedTasks, setSelectedTasks] = useState<string[]>([]);
  const [revisionStartedAt, setRevisionStartedAt] = useState<number | null>(
    null,
  );
  const [isFeedbackPending, setIsFeedbackPending] = useState(false);
  const [isRevisionPending, setIsRevisionPending] = useState(false);
  const [error, setError] = useState("");

  function abortFeedbackStream() {
    feedbackAbortControllerRef.current?.abort();
    feedbackAbortControllerRef.current = null;
  }

  function advancePrewritingFeedbackEpoch() {
    const nextEpoch = prewritingFeedbackEpochRef.current + 1;
    prewritingFeedbackEpochRef.current = nextEpoch;
    setPrewritingFeedbackEpoch(nextEpoch);
  }

  function handleModeChange(nextMode: WritingCastleMode) {
    if (nextMode === mode) {
      return;
    }
    feedbackRequestId.current += 1;
    advancePrewritingFeedbackEpoch();
    abortFeedbackStream();
    if (isFeedbackPending) {
      setEssayId(null);
      setFirstDraftId(null);
      setBaseVersionId(null);
      setCurrentRoundIndex(null);
      setFirstDraftReaction(null);
      setFeedback(null);
      setSelectedTasks([]);
      setComparison(null);
      setSettlement(null);
      setRevisionResultId(null);
      setRevisionResultReaction(null);
    }
    setIsFeedbackPending(false);
    setError("");
    setMode(nextMode);
  }

  useEffect(() => {
    activeStudentId.current = studentId;

    return () => {
      activeStudentId.current = null;
      abortFeedbackStream();
    };
  }, [studentId]);

  function toggleTask(instruction: string) {
    const nextSelectedTasks = selectedTasks.includes(instruction)
      ? selectedTasks.filter((item) => item !== instruction)
      : [...selectedTasks, instruction];
    clearStaleRevisionAttemptForPayload(revision, nextSelectedTasks);
    setSelectedTasks(nextSelectedTasks);
  }

  function buildRevisionPayloadSnapshot(content: string, completedTasks: string[]) {
    const allTasks =
      feedback?.revision_tasks.map((task) => task.instruction) ?? [];

    return {
      content,
      completedTasks,
      skippedTasks: allTasks.filter((task) => !completedTasks.includes(task)),
    };
  }

  function arraysEqual(left: string[], right: string[]) {
    return left.length === right.length && left.every((item, index) => item === right[index]);
  }

  function clearRevisionSubmitAttempt() {
    revisionSubmitKeyRef.current = null;
    pendingRevisionPayload.current = null;
    setRevisionSubmitKey(null);
  }

  function clearStaleRevisionAttemptForPayload(
    content: string,
    completedTasks: string[],
  ) {
    if (!revisionSubmitKeyRef.current) {
      if (error) {
        setError("");
      }
      return;
    }

    const pendingPayload = pendingRevisionPayload.current;
    const nextPayload = buildRevisionPayloadSnapshot(content, completedTasks);
    const isSamePayload =
      pendingPayload !== null &&
      pendingPayload.content === nextPayload.content &&
      arraysEqual(pendingPayload.completedTasks, nextPayload.completedTasks) &&
      arraysEqual(pendingPayload.skippedTasks, nextPayload.skippedTasks);

    if (!isSamePayload) {
      clearRevisionSubmitAttempt();
      if (error) {
        setError("");
      }
    }
  }

  function applyFeedbackResult(result: EssayResponse, submittedTitle = title, submittedDraft = draft) {
    setEssayId(result.essay.id);
    setFirstDraftId(result.first_draft?.id ?? null);
    setBaseVersionId(result.first_draft?.id ?? null);
    setCurrentRoundIndex(2);
    clearRevisionSubmitAttempt();
    setFirstDraftReaction(result.first_draft?.reaction ?? null);
    setFeedback(result.feedback);
    setSelectedTasks(
      result.feedback.revision_tasks.map((task) => task.instruction),
    );
    setRevisionStartedAt(getCurrentTimeMs());
    setRevision("");
    loadedDirectInput.current = { title: submittedTitle, draft: submittedDraft };
    loadedRevision.current = "";
    setHasUnsubmittedRevisionInput(false);
    setHasUnsubmittedDirectInput(false);
    setComparison(null);
    setSettlement(null);
    setRevisionResultId(null);
    setRevisionResultReaction(null);
    setError("");
  }

  async function handleFeedbackSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestId = feedbackRequestId.current + 1;
    feedbackRequestId.current = requestId;
    revisionRequestId.current += 1;
    isRevisionSubmitting.current = false;
    setIsRevisionPending(false);
    clearRevisionSubmitAttempt();
    advancePrewritingFeedbackEpoch();
    abortFeedbackStream();
    setIsFeedbackPending(true);
    setError("");
    const requestStudentId = studentId;
    const submittedTitle = title;
    const submittedDraft = draft;
    const clientSubmissionId = createClientSubmissionId();

    try {
      let result: EssayResponse | null = null;

      if (isEssayFeedbackStreamingEnabled()) {
        let streamState: StreamReducerState | undefined;
        let sawPreview = false;
        const abortController = new AbortController();
        feedbackAbortControllerRef.current = abortController;
        const isCurrentFeedbackRequest = () =>
          activeStudentId.current === requestStudentId &&
          feedbackRequestId.current === requestId &&
          !abortController.signal.aborted;

        try {
          await streamEssayFeedback(
            studentId,
            {
              title: submittedTitle,
              draft: submittedDraft,
              entry: "existing_draft",
              client_submission_id: clientSubmissionId,
            },
            (frame) => {
              if (!isCurrentFeedbackRequest()) {
                return;
              }
              streamState = reduceStreamEvent(streamState, frame);
              if (frame.event === "feedback_section_preview" && streamState) {
                sawPreview = true;
                const previewFeedback = previewFeedbackFromStream(streamState);
                setFeedback(previewFeedback);
                setSelectedTasks(
                  previewFeedback.revision_tasks.map((task) => task.instruction),
                );
                setComparison(null);
                setSettlement(null);
                setRevisionResultId(null);
                setRevisionResultReaction(null);
              }
            },
            { signal: abortController.signal },
          );
        } catch (error) {
          if (!isCurrentFeedbackRequest()) {
            return;
          }
          if (sawPreview) {
            throw error;
          }
          result = await createEssay(studentId, {
            title: submittedTitle,
            draft: submittedDraft,
            entry: "existing_draft",
            client_submission_id: createClientSubmissionId(),
          });
        }

        if (!result) {
          if (!isCurrentFeedbackRequest()) {
            return;
          }
          if (!streamState?.fetchUrl) {
            throw new Error("stream completed without a feedback result URL");
          }
          result = await fetchEssayFeedbackResult(streamState.fetchUrl);
        }
      } else {
        result = await createEssay(studentId, {
          title: submittedTitle,
          draft: submittedDraft,
          entry: "existing_draft",
          client_submission_id: clientSubmissionId,
        });
      }

      if (
        activeStudentId.current !== requestStudentId ||
        feedbackRequestId.current !== requestId
      ) {
        return;
      }
      applyFeedbackResult(result, submittedTitle, submittedDraft);
    } catch {
      if (
        activeStudentId.current !== requestStudentId ||
        feedbackRequestId.current !== requestId
      ) {
        return;
      }
      setError("这次提交没有成功。先别急，检查一下网络后再试一次。");
    } finally {
      if (
        activeStudentId.current === requestStudentId &&
        feedbackRequestId.current === requestId
      ) {
        if (feedbackAbortControllerRef.current?.signal.aborted === false) {
          feedbackAbortControllerRef.current = null;
        }
        setIsFeedbackPending(false);
      }
    }
  }

  function handlePrewritingFeedback(
    result: EssayResponse,
    feedbackEpoch = prewritingFeedbackEpochRef.current,
  ) {
    if (feedbackEpoch !== prewritingFeedbackEpochRef.current) {
      return;
    }
    applyFeedbackResult(result);
  }

  async function handleRevisionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isRevisionSubmitting.current) {
      return;
    }
    if (!essayId || settlement) {
      return;
    }
    if (!baseVersionId) {
      setError("这次提交没有成功。先别急，检查一下网络后再试一次。");
      return;
    }

    isRevisionSubmitting.current = true;
    const requestId = revisionRequestId.current + 1;
    revisionRequestId.current = requestId;
    const submittedEssayId = essayId;
    const submittedBaseVersionId = baseVersionId;
    const submittedRevision = revision;
    setIsRevisionPending(true);
    setIsFeedbackPending(false);
    setError("");
    const requestStudentId = studentId;

    try {
      const submittedPayload = buildRevisionPayloadSnapshot(
        submittedRevision,
        selectedTasks,
      );
      const durationSeconds =
        revisionStartedAt === null
          ? null
          : Math.max(0, Math.round((getCurrentTimeMs() - revisionStartedAt) / 1000));
      const idempotencyKey =
        revisionSubmitKeyRef.current ?? globalThis.crypto.randomUUID();
      revisionSubmitKeyRef.current = idempotencyKey;
      pendingRevisionPayload.current = submittedPayload;
      setRevisionSubmitKey(idempotencyKey);
      const result = await submitEssayRevision(submittedEssayId, {
        base_version_id: submittedBaseVersionId,
        content: submittedPayload.content,
        idempotency_key: idempotencyKey,
        completed_tasks: submittedPayload.completedTasks,
        skipped_tasks: submittedPayload.skippedTasks,
        duration_seconds: durationSeconds,
      });

      if (
        activeStudentId.current !== requestStudentId ||
        revisionRequestId.current !== requestId
      ) {
        return;
      }
      if (!("revision" in result)) {
        setError(result.message);
        return;
      }
      setComparison(result.comparison);
      setSettlement(result.settlement);
      setRevisionResultId(result.revision.id);
      setRevisionResultReaction(result.revision.reaction ?? null);
      clearRevisionSubmitAttempt();
      loadedRevision.current = submittedRevision;
      setHasUnsubmittedRevisionInput(false);
    } catch {
      if (
        activeStudentId.current !== requestStudentId ||
        revisionRequestId.current !== requestId
      ) {
        return;
      }
      setError("这次提交没有成功。先别急，检查一下网络后再试一次。");
    } finally {
      if (
        activeStudentId.current === requestStudentId &&
        revisionRequestId.current === requestId
      ) {
        isRevisionSubmitting.current = false;
        setIsRevisionPending(false);
      }
    }
  }

  async function handleArchiveSelect(selectedEssayId: string) {
    const hasUnsavedRevisionInput = revision !== loadedRevision.current;
    const hasUnsavedDirectInput = hasUnsubmittedDirectInput;
    if (hasUnsavedRevisionInput || hasUnsavedDirectInput) {
      const confirmed = window.confirm("这段还没有提交，要先打开另一篇作文吗？");
      if (!confirmed) {
        return;
      }
    }

    setError("");
    feedbackRequestId.current += 1;
    advancePrewritingFeedbackEpoch();
    abortFeedbackStream();
    setIsFeedbackPending(false);
    revisionRequestId.current += 1;
    isRevisionSubmitting.current = false;
    setIsRevisionPending(false);
    const requestId = archiveSelectionRequestId.current + 1;
    archiveSelectionRequestId.current = requestId;
    try {
      const detail = await fetchEssayArchiveDetail(selectedEssayId);
      if (
        archiveSelectionRequestId.current !== requestId ||
        detail.essay_id !== selectedEssayId ||
        activeStudentId.current !== studentId
      ) {
        return;
      }
      if (!detail.can_continue_revision || !detail.continue_revision) {
        setArchiveOpen(false);
        setError("这篇作文现在还不能继续修改。");
        return;
      }
      setEssayId(detail.essay_id);
      setTitle(detail.title);
      setDraft("");
      setFirstDraftId(null);
      setFirstDraftReaction(null);
      setRevision(detail.continue_revision.latest_content);
      loadedDirectInput.current = { title: detail.title, draft: "" };
      loadedRevision.current = detail.continue_revision.latest_content;
      setBaseVersionId(detail.continue_revision.latest_version_id);
      setCurrentRoundIndex(detail.continue_revision.next_round_index);
      setFeedback({
        strengths: [detail.continue_revision.previous_ai_guidance],
        improvements: [],
        problem_monsters: [],
        sentence_notes: [],
        revision_tasks: [],
      });
      setSelectedTasks([]);
      setRevisionStartedAt(getCurrentTimeMs());
      setSettlement(null);
      setComparison(null);
      setRevisionResultId(null);
      setRevisionResultReaction(null);
      clearRevisionSubmitAttempt();
      setHasUnsubmittedRevisionInput(false);
      setHasUnsubmittedDirectInput(false);
      setAiTopicEssay(null);
      setArchiveOpen(false);
    } catch {
      if (
        archiveSelectionRequestId.current !== requestId ||
        activeStudentId.current !== studentId
      ) {
        return;
      }
      setArchiveOpen(false);
      setError("这篇作文暂时没有打开成功，可以再试一次。");
    }
  }

  function resetForNewEssay() {
    feedbackRequestId.current += 1;
    advancePrewritingFeedbackEpoch();
    abortFeedbackStream();
    revisionRequestId.current += 1;
    isRevisionSubmitting.current = false;
    setTitle("");
    setDraft("");
    setRevision("");
    loadedDirectInput.current = { title: "", draft: "" };
    loadedRevision.current = "";
    setEssayId(null);
    setBaseVersionId(null);
    setCurrentRoundIndex(null);
    setFeedback(null);
    setComparison(null);
    setSettlement(null);
    setAiTopicEssay(null);
    clearRevisionSubmitAttempt();
    setFirstDraftId(null);
    setFirstDraftReaction(null);
    setRevisionResultId(null);
    setRevisionResultReaction(null);
    setSelectedTasks([]);
    setHasUnsubmittedRevisionInput(false);
    setHasUnsubmittedDirectInput(false);
    setIsFeedbackPending(false);
    setIsRevisionPending(false);
    setError("");
  }

  function handleTitleChange(value: string) {
    setTitle(value);
    setHasUnsubmittedDirectInput(
      value !== loadedDirectInput.current.title ||
        draft !== loadedDirectInput.current.draft,
    );
  }

  function handleDraftChange(value: string) {
    setDraft(value);
    setHasUnsubmittedDirectInput(
      title !== loadedDirectInput.current.title ||
        value !== loadedDirectInput.current.draft,
    );
  }

  function handleRevisionChange(value: string) {
    setRevision(value);
    const isDirty = value !== loadedRevision.current;
    setHasUnsubmittedRevisionInput(isDirty);
    clearStaleRevisionAttemptForPayload(value, selectedTasks);
  }

  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <button
        className="fixed right-4 top-24 z-20 inline-flex items-center gap-2 rounded-lg border border-[var(--wen-border)] bg-white px-4 py-2 font-semibold shadow-sm"
        type="button"
        onClick={() => setArchiveOpen(true)}
      >
        <Archive size={18} aria-hidden="true" />
        作文档案
      </button>
      <EssayArchiveDrawer
        studentId={studentId}
        open={archiveOpen}
        onOpenChange={setArchiveOpen}
        onSelectEssay={handleArchiveSelect}
      />
      <main className="min-h-screen px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <nav
          aria-label="页面导航"
          className="mb-4 flex flex-wrap gap-3 text-sm font-bold"
        >
          <Link
            className="rounded-lg border border-[var(--wen-border)] px-4 py-2"
            href={`/children/${studentId}`}
          >
            回到 Dashboard
          </Link>
          <Link
            className="rounded-lg border border-[var(--wen-border)] px-4 py-2"
            href="/parent/children"
          >
            返回孩子列表
          </Link>
        </nav>
        {shouldShowAssessmentRecommendation ? (
          <AssessmentRecommendationCard
            studentId={studentId}
            continueLabel="今天先写作文"
            onContinue={dismissAssessmentRecommendation}
          />
        ) : null}

        <WritingCastleModeShell mode={mode} onModeChange={handleModeChange} />

        {mode === "classroom" && !feedback ? (
          <ClassroomPrewritingWizard
            studentId={studentId}
            onFeedback={handlePrewritingFeedback}
            feedbackEpoch={prewritingFeedbackEpoch}
          />
        ) : null}

        {mode === "ai_topic" && !feedback && !aiTopicEssay ? (
          <AiTopicIdeaFlow
            studentId={studentId}
            onEssayCreated={setAiTopicEssay}
          />
        ) : null}

        {mode === "ai_topic" && !feedback && aiTopicEssay ? (
          <ClassroomPrewritingWizard
            studentId={studentId}
            initialEssay={aiTopicEssay}
            skipActiveResume
            onEssayChange={setAiTopicEssay}
            onFeedback={handlePrewritingFeedback}
            feedbackEpoch={prewritingFeedbackEpoch}
          />
        ) : null}

        {mode === "direct" || feedback ? (
        <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Sparkles
              size={22}
              aria-hidden="true"
              className="text-[var(--wen-orange)]"
            />
            <h1 className="text-2xl font-bold">作文修改</h1>
          </div>
          <form className="mt-5 space-y-4" onSubmit={handleFeedbackSubmit}>
            <label className="block font-semibold">
              作文题目
              <input
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                value={title}
                onChange={(event) => handleTitleChange(event.target.value)}
              />
            </label>
            <label className="block font-semibold">
              初稿
              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                value={draft}
                onChange={(event) => handleDraftChange(event.target.value)}
              />
            </label>
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white disabled:opacity-60"
              type="submit"
              disabled={isFeedbackPending}
            >
              {isFeedbackPending ? (
                <Loader2
                  size={18}
                  aria-hidden="true"
                  className="animate-spin"
                />
              ) : null}
              获得点评
            </button>
          </form>
        </section>
        ) : null}

        {feedback ? (
          <section
            aria-label="作文点评"
            className="space-y-4"
          >
            <h2 className="text-xl font-bold">作文点评</h2>
            <FeedbackTextSection title="写得好的地方" items={feedback.strengths} />
            <FeedbackTextSection title="可以改进的地方" items={feedback.improvements} />
            <FeedbackTextSection title="句子小提示" items={feedback.sentence_notes} />
            <h3 className="mt-6 font-semibold">修改小任务</h3>
            <div className="mt-3 space-y-3">
              {feedback.revision_tasks.map((task) => (
                <label
                  key={`${task.target}-${task.instruction}`}
                  className="flex gap-3 rounded-lg border border-[var(--wen-border)] bg-white p-4 shadow-sm"
                >
                  <input
                    type="checkbox"
                    checked={selectedTasks.includes(task.instruction)}
                    onChange={() => toggleTask(task.instruction)}
                    aria-label={task.instruction}
                    className="mt-1 h-5 w-5"
                  />
                  <span>
                    <span className="block text-sm text-[var(--wen-muted)]">
                      {task.target}
                    </span>
                    <span className="font-semibold">{task.instruction}</span>
                  </span>
                </label>
              ))}
            </div>
            {firstDraftId ? (
              <FeedbackReaction
                key={`${studentId}:essay_draft:${firstDraftId}`}
                studentId={studentId}
                targetType="essay_draft"
                targetId={firstDraftId}
                initialReaction={firstDraftReaction ?? null}
              />
            ) : null}
            <button
              className="mt-4 rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
              type="button"
              onClick={resetForNewEssay}
            >
              写新的作文
            </button>
          </section>
        ) : null}

        {mode === "direct" || feedback ? (
        <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
          {currentRoundIndex ? (
            <p className="mb-3 text-sm font-semibold text-[var(--wen-muted)]">
              正在写第 {currentRoundIndex} 稿
            </p>
          ) : null}
          <form className="space-y-4" onSubmit={handleRevisionSubmit}>
            <label className="block font-semibold">
              下一稿
              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                disabled={isRevisionPending}
                value={revision}
                onChange={(event) => handleRevisionChange(event.target.value)}
              />
            </label>
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-leaf)] px-4 py-2 font-semibold text-white disabled:opacity-60"
              type="submit"
              disabled={!essayId || isRevisionPending || settlement !== null}
            >
              {isRevisionPending ? (
                <Loader2
                  size={18}
                  aria-hidden="true"
                  className="animate-spin"
                />
              ) : null}
              提交下一稿
            </button>
          </form>
        </section>
        ) : null}

        {comparison ? (
          <section
            aria-label="修改对比"
            className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
          >
            <h2 className="text-xl font-bold">修改对比</h2>
            <p className="mt-3">{comparison.encouragement}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {comparison.improved_dimensions.map((dimension) => (
                <p
                  key={dimension}
                  className="rounded-lg bg-[var(--wen-bg)] px-3 py-2 font-semibold"
                >
                  {dimension}
                </p>
              ))}
            </div>
            {comparison && revisionResultId ? (
              <div className="mt-5">
                <FeedbackReaction
                  key={`${studentId}:essay_revision:${revisionResultId}`}
                  studentId={studentId}
                  targetType="essay_revision"
                  targetId={revisionResultId}
                  initialReaction={revisionResultReaction ?? null}
                />
              </div>
            ) : null}
            <button
              className="mt-5 rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
              type="button"
              onClick={resetForNewEssay}
            >
              写新的作文
            </button>
          </section>
        ) : null}
        {settlement ? <SettlementPanel settlement={settlement} /> : null}
        {isFeedbackPending ? (
          <p role="status">AI 教练正在读你的初稿</p>
        ) : null}
        {isRevisionPending ? (
          <p role="status">AI 教练正在比较这次修改</p>
        ) : null}
        {error ? (
          <p
            className="rounded-lg border border-[var(--wen-orange)] bg-white p-4 font-semibold"
            role="alert"
          >
            {error}
          </p>
        ) : null}
      </div>
      </main>
    </>
  );
}

function FeedbackTextSection({
  title,
  items,
}: {
  title: string;
  items?: string[];
}) {
  if (!items?.length) {
    return null;
  }

  return (
    <section className="space-y-2">
      <h3 className="font-semibold">{title}</h3>
      <div className="space-y-2">
        {items.map((item) => (
          <p key={item} className="flex items-start gap-2">
            <CheckCircle2
              size={18}
              aria-hidden="true"
              className="mt-1 text-[var(--wen-leaf)]"
            />
            <span>{item}</span>
          </p>
        ))}
      </div>
    </section>
  );
}
