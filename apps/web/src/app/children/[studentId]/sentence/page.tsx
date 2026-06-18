"use client";

import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { AiWaitingStatus } from "../../../../components/AiWaitingStatus";
import { AssessmentRecommendationCard } from "../../../../components/AssessmentRecommendationCard";
import { FamilyTopbar } from "../../../../components/FamilyTopbar";
import { FeedbackReaction } from "../../../../components/FeedbackReaction";
import { SettlementPanel } from "../../../../components/SettlementPanel";
import {
  ApiRequestError,
  completeSentenceChallenge,
  createSentenceChallenge,
  createSentenceTraining,
  type SentenceFocus,
  type SentenceTrainingResponse,
} from "../../../../lib/api";
import { useAssessmentRecommendation } from "../../../../lib/useAssessmentRecommendation";
import type {
  SentenceChallenge,
  SentenceChallengeCompletionResponse,
} from "../../../../lib/types";

const DEFAULT_SENTENCE_FOCUS: SentenceFocus = "加细节";
type Mode = "challenge" | "free_input";
type AIInteractionState =
  | "idle"
  | "generating"
  | "validating"
  | "fallback"
  | "completed"
  | "failed";

const DAILY_LIMIT_MESSAGE =
  "今天的句子挑战已经完成很多啦，休息一下，明天继续闯关！";
const CHALLENGE_LOAD_ERROR_MESSAGE =
  "这次句子挑战没有准备成功。可以先自己带句子来练。";
const SENTENCE_SUBMIT_ERROR_MESSAGE =
  "这次句子练习没有提交成功。先别急，检查一下网络后再试一次。";
const CHALLENGE_LOADING_MESSAGES = [
  "正在出题...",
  "AI 教练正在想一个适合你的句子...",
  "快好了！",
] as const;
const FEEDBACK_LOADING_MESSAGES = [
  "AI 教练正在读你的句子...",
  "正在找出你写得好的地方...",
  "马上给你一个小建议。",
] as const;

export default function SentencePage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);

  return <SentencePageContent key={studentId} studentId={studentId} />;
}

function SentencePageContent({ studentId }: { studentId: string }) {
  const activeStudentId = useRef<string | null>(studentId);
  const interactionVersion = useRef(0);
  const {
    shouldShowAssessmentRecommendation,
    dismissAssessmentRecommendation,
  } = useAssessmentRecommendation(studentId);
  const [mode, setMode] = useState<Mode>("challenge");
  const [challenge, setChallenge] = useState<SentenceChallenge | null>(null);
  const [challengeResult, setChallengeResult] =
    useState<SentenceChallengeCompletionResponse | null>(null);
  const [freeInputResult, setFreeInputResult] =
    useState<SentenceTrainingResponse | null>(null);
  const [sourceSentence, setSourceSentence] = useState("");
  const [upgradedSentence, setUpgradedSentence] = useState("");
  const [aiState, setAiState] = useState<AIInteractionState>("generating");
  const [error, setError] = useState("");
  const isLoadingChallenge = aiState === "generating";
  const isSubmitting = aiState === "validating" || aiState === "fallback";

  useEffect(() => {
    let active = true;
    activeStudentId.current = studentId;
    const requestVersion = interactionVersion.current + 1;
    interactionVersion.current = requestVersion;
    setAiState("generating");

    createSentenceChallenge(studentId)
      .then((response) => {
        if (
          active &&
          activeStudentId.current === studentId &&
          interactionVersion.current === requestVersion
        ) {
          setChallenge(response.challenge);
          setAiState("idle");
        }
      })
      .catch((error) => {
        if (
          active &&
          activeStudentId.current === studentId &&
          interactionVersion.current === requestVersion
        ) {
          setError(
            error instanceof ApiRequestError && error.status === 429
              ? DAILY_LIMIT_MESSAGE
              : CHALLENGE_LOAD_ERROR_MESSAGE,
          );
          setAiState("failed");
        }
      });

    return () => {
      active = false;
      activeStudentId.current = null;
    };
  }, [studentId]);

  async function handleChallengeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) {
      return;
    }

    const requestVersion = interactionVersion.current + 1;
    interactionVersion.current = requestVersion;
    setAiState("validating");
    setError("");
    const requestStudentId = studentId;
    const requestTrainingId = challenge.id;

    try {
      const response = await completeSentenceChallenge(studentId, requestTrainingId, {
        upgraded_sentence: upgradedSentence,
      });
      if (
        activeStudentId.current === requestStudentId &&
        interactionVersion.current === requestVersion
      ) {
        setChallengeResult(response);
        setAiState("completed");
      }
    } catch {
      if (
        activeStudentId.current === requestStudentId &&
        interactionVersion.current === requestVersion
      ) {
        setError(SENTENCE_SUBMIT_ERROR_MESSAGE);
        setAiState("failed");
      }
    }
  }

  async function handleFreeInputSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestVersion = interactionVersion.current + 1;
    interactionVersion.current = requestVersion;
    setAiState("validating");
    setError("");
    setFreeInputResult(null);
    const requestStudentId = studentId;

    try {
      const result = await createSentenceTraining(studentId, {
        source_sentence: sourceSentence,
        upgraded_sentence: upgradedSentence,
        focus: DEFAULT_SENTENCE_FOCUS,
      });

      if (
        activeStudentId.current !== requestStudentId ||
        interactionVersion.current !== requestVersion
      ) {
        return;
      }
      setFreeInputResult(result);
      setAiState("completed");
    } catch {
      if (
        activeStudentId.current !== requestStudentId ||
        interactionVersion.current !== requestVersion
      ) {
        return;
      }
      setError(SENTENCE_SUBMIT_ERROR_MESSAGE);
      setAiState("failed");
    }
  }

  async function handleRefreshChallenge() {
    if (isSubmitting) {
      return;
    }

    const requestVersion = interactionVersion.current + 1;
    interactionVersion.current = requestVersion;
    setMode("challenge");
    setChallenge(null);
    setChallengeResult(null);
    setFreeInputResult(null);
    setSourceSentence("");
    setUpgradedSentence("");
    setError("");
    setAiState("generating");
    const requestStudentId = studentId;

    try {
      const response = await createSentenceChallenge(studentId);
      if (
        activeStudentId.current === requestStudentId &&
        interactionVersion.current === requestVersion
      ) {
        setChallenge(response.challenge);
        setAiState("idle");
      }
    } catch (error) {
      if (
        activeStudentId.current === requestStudentId &&
        interactionVersion.current === requestVersion
      ) {
        setError(
          error instanceof ApiRequestError && error.status === 429
            ? DAILY_LIMIT_MESSAGE
            : CHALLENGE_LOAD_ERROR_MESSAGE,
        );
        setAiState("failed");
      }
    }
  }

  function handleSwitchToFreeInput() {
    if (isSubmitting) {
      return;
    }

    interactionVersion.current += 1;
    setMode("free_input");
    setChallengeResult(null);
    setFreeInputResult(null);
    setSourceSentence("");
    setUpgradedSentence("");
    setError("");
    setAiState("idle");
  }

  const result = mode === "challenge" ? challengeResult : freeInputResult;

  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <main className="px-5 py-8 sm:px-8">
        <div className="mx-auto max-w-4xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm sm:p-8">
          <div className="mb-6 flex items-start gap-3">
            <span className="rounded-lg bg-[var(--wen-orange-soft)] p-2 text-[var(--wen-orange)]">
              <Sparkles aria-hidden="true" className="h-6 w-6" />
            </span>
            <div>
              <h1 className="text-2xl font-bold">句子工坊</h1>
              <p className="mt-2 text-sm text-[var(--wen-muted)]">
                把一句话升级成小画面
              </p>
            </div>
          </div>

          {shouldShowAssessmentRecommendation ? (
            <div className="mb-5">
              <AssessmentRecommendationCard
                studentId={studentId}
                continueLabel="今天先练句子"
                onContinue={dismissAssessmentRecommendation}
              />
            </div>
          ) : null}

          {mode === "challenge" ? (
            <div className="space-y-5">
              {isLoadingChallenge ? (
                <AiWaitingStatus messages={CHALLENGE_LOADING_MESSAGES} />
              ) : null}

              {challenge ? (
                <section className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-5">
                  <p className="text-xs font-bold text-[var(--wen-muted)]">
                    {challenge.grade_label} · {challenge.difficulty_label} ·{" "}
                    {challenge.focus}
                  </p>
                  <p className="mt-3 text-xl font-bold">{challenge.source_sentence}</p>
                  <p className="mt-3 text-sm font-semibold">
                    {challenge.challenge_prompt}
                  </p>
                  <p className="mt-2 text-sm text-[var(--wen-muted)]">
                    {challenge.hint}
                  </p>
                </section>
              ) : null}

              {!challengeResult ? (
                <form className="space-y-5" onSubmit={handleChallengeSubmit}>
                  <label className="block text-sm font-semibold">
                    升级后的句子
                    <textarea
                      className="mt-2 min-h-32 w-full rounded-lg border border-[var(--wen-border)] px-4 py-3 text-base outline-none transition focus:border-[var(--wen-orange)]"
                      placeholder="试着把挑战句写得更具体。"
                      value={upgradedSentence}
                      onChange={(event) => setUpgradedSentence(event.target.value)}
                    />
                  </label>
                  <div className="flex flex-wrap gap-3">
                    <button
                      className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 text-sm font-bold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
                      type="submit"
                      disabled={isSubmitting || !challenge}
                    >
                      {isSubmitting ? (
                        <Loader2
                          aria-hidden="true"
                          className="h-4 w-4 animate-spin"
                        />
                      ) : null}
                      提交给 AI 教练
                    </button>
                    <button
                      className="rounded-lg border border-[var(--wen-border)] px-5 py-3 text-sm font-bold"
                      type="button"
                      onClick={handleSwitchToFreeInput}
                      disabled={isSubmitting}
                    >
                      自己带句子来练
                    </button>
                  </div>
                </form>
              ) : null}
            </div>
          ) : (
            <form className="space-y-5" onSubmit={handleFreeInputSubmit}>
              <label className="block text-sm font-semibold">
                原句
                <textarea
                  className="mt-2 min-h-28 w-full rounded-lg border border-[var(--wen-border)] px-4 py-3 text-base outline-none transition focus:border-[var(--wen-orange)]"
                  placeholder="例如：公园很美。"
                  value={sourceSentence}
                  onChange={(event) => setSourceSentence(event.target.value)}
                />
              </label>
              <label className="block text-sm font-semibold">
                升级后的句子
                <textarea
                  className="mt-2 min-h-32 w-full rounded-lg border border-[var(--wen-border)] px-4 py-3 text-base outline-none transition focus:border-[var(--wen-orange)]"
                  placeholder="试着加一个动作、颜色、声音或比喻。"
                  value={upgradedSentence}
                  onChange={(event) => setUpgradedSentence(event.target.value)}
                />
              </label>
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 text-sm font-bold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : null}
                提交给 AI 教练
              </button>
            </form>
          )}

          {isSubmitting ? (
            <div className="mt-4">
              <AiWaitingStatus messages={FEEDBACK_LOADING_MESSAGES} />
              <span className="sr-only">AI 教练正在看你的句子</span>
            </div>
          ) : null}
          {error ? (
            <p
              className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
              role="alert"
            >
              {error}
            </p>
          ) : null}
          {result ? (
            <div className="mt-8 space-y-6">
              {mode === "challenge" && challengeResult ? (
                <section
                  aria-label="AI 教练反馈"
                  className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-5"
                >
                  <h2 className="text-xl font-bold">AI 教练反馈</h2>
                  <p className="mt-3 text-base font-semibold">
                    {challengeResult.feedback.encouragement}
                  </p>
                  <p className="mt-2 text-sm text-[var(--wen-muted)]">
                    {challengeResult.feedback.highlight}
                  </p>
                  <p className="mt-2 text-sm">
                    {challengeResult.feedback.suggestion}
                  </p>
                  <p className="mt-4 text-xs font-bold text-[var(--wen-muted)]">
                    这是一个参考写法，你的写法也很棒。
                  </p>
                  <p className="mt-2 text-sm font-semibold">
                    {challengeResult.feedback.example_upgrade}
                  </p>
                </section>
              ) : null}

              {mode === "free_input" && freeInputResult ? (
                <section
                  aria-label="AI 教练反馈"
                  className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-5"
                >
                  <h2 className="text-xl font-bold">AI 教练反馈</h2>
                  <p className="mt-3 text-base font-semibold">
                    {freeInputResult.feedback.encouragement}
                  </p>
                  <p className="mt-2 text-sm text-[var(--wen-muted)]">
                    {freeInputResult.feedback.specific_improvement}
                  </p>

                  <h3 className="mt-5 text-sm font-bold">发现的问题怪兽</h3>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {freeInputResult.feedback.problem_monsters.map((monster) => (
                      <span
                        className="rounded-lg bg-white px-3 py-1 text-sm font-semibold text-[var(--wen-orange)]"
                        key={monster}
                      >
                        {monster}
                      </span>
                    ))}
                  </div>

                  <h3 className="mt-5 text-sm font-bold">下一小步</h3>
                  <p className="mt-2 text-sm">{freeInputResult.feedback.next_step}</p>
                </section>
              ) : null}
              <FeedbackReaction
                key={`${studentId}:sentence_training:${result.training.id}`}
                studentId={studentId}
                targetType="sentence_training"
                targetId={result.training.id}
                initialReaction={result.training.reaction ?? null}
              />
              <SettlementPanel settlement={result.settlement} />
              {mode === "challenge" ? (
                <div className="flex flex-wrap gap-3">
                  <button
                    className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 text-sm font-bold text-white"
                    type="button"
                    onClick={handleRefreshChallenge}
                    disabled={isSubmitting}
                  >
                    再挑战一题
                  </button>
                  <button
                    className="rounded-lg border border-[var(--wen-border)] px-4 py-2 text-sm font-bold"
                    type="button"
                    onClick={handleSwitchToFreeInput}
                    disabled={isSubmitting}
                  >
                    自己带句子来练
                  </button>
                </div>
              ) : null}
              <nav
                aria-label="句子任务下一步"
                className="flex flex-wrap gap-3 text-sm font-bold"
              >
                <Link
                  className="rounded-lg border border-[var(--wen-border)] px-4 py-2"
                  href={`/children/${studentId}`}
                >
                  回到 Dashboard
                </Link>
                <Link
                  className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 text-white"
                  href={`/parent/${studentId}/report`}
                >
                  给家长看报告
                </Link>
                <Link
                  className="rounded-lg border border-[var(--wen-border)] px-4 py-2"
                  href="/parent/children"
                >
                  返回孩子列表
                </Link>
              </nav>
            </div>
          ) : null}
        </div>
      </main>
    </>
  );
}
