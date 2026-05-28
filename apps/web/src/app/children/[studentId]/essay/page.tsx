"use client";

import { use, useState } from "react";
import type { FormEvent } from "react";
import { CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { FamilyTopbar } from "../../../../components/FamilyTopbar";
import { FeedbackReaction } from "../../../../components/FeedbackReaction";
import { SettlementPanel } from "../../../../components/SettlementPanel";
import {
  createEssay,
  submitEssayRevision,
  type EssayResponse,
  type EssayRevisionResponse,
  type Settlement,
} from "../../../../lib/api";

export default function EssayPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const [title, setTitle] = useState("");
  const [draft, setDraft] = useState("");
  const [revision, setRevision] = useState("");
  const [essayId, setEssayId] = useState<string | null>(null);
  const [firstDraftId, setFirstDraftId] = useState<string | null>(null);
  const [revisionResultId, setRevisionResultId] = useState<string | null>(null);
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

  function toggleTask(instruction: string) {
    setSelectedTasks((current) =>
      current.includes(instruction)
        ? current.filter((item) => item !== instruction)
        : [...current, instruction],
    );
  }

  async function handleFeedbackSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsFeedbackPending(true);
    setError("");

    try {
      const result = await createEssay(studentId, {
        title,
        draft,
        entry: "existing_draft",
      });

      setEssayId(result.essay.id);
      setFirstDraftId(result.first_draft?.id ?? null);
      setFeedback(result.feedback);
      setSelectedTasks(
        result.feedback.revision_tasks.map((task) => task.instruction),
      );
      setRevisionStartedAt(Date.now());
      setRevision("");
      setComparison(null);
      setSettlement(null);
      setRevisionResultId(null);
    } catch {
      setError("这次提交没有成功。先别急，检查一下网络后再试一次。");
    } finally {
      setIsFeedbackPending(false);
    }
  }

  async function handleRevisionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!essayId || settlement) {
      return;
    }

    setIsRevisionPending(true);
    setIsFeedbackPending(false);
    setError("");

    try {
      const allTasks =
        feedback?.revision_tasks.map((task) => task.instruction) ?? [];
      const skippedTasks = allTasks.filter(
        (task) => !selectedTasks.includes(task),
      );
      const durationSeconds =
        revisionStartedAt === null
          ? null
          : Math.max(0, Math.round((Date.now() - revisionStartedAt) / 1000));
      const result = await submitEssayRevision(essayId, {
        content: revision,
        completed_tasks: selectedTasks,
        skipped_tasks: skippedTasks,
        duration_seconds: durationSeconds,
      });

      setComparison(result.comparison);
      setSettlement(result.settlement);
      setRevisionResultId(result.revision.id);
    } catch {
      setError("这次提交没有成功。先别急，检查一下网络后再试一次。");
    } finally {
      setIsRevisionPending(false);
    }
  }

  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <main className="min-h-screen px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
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
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label className="block font-semibold">
              初稿
              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
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

        {feedback ? (
          <section
            aria-label="作文点评"
            className="space-y-4"
          >
            <h2 className="text-xl font-bold">作文点评</h2>
            <div className="mt-4 space-y-2">
              {feedback.strengths.map((strength) => (
                <p key={strength} className="flex items-start gap-2">
                  <CheckCircle2
                    size={18}
                    aria-hidden="true"
                    className="mt-1 text-[var(--wen-leaf)]"
                  />
                  <span>{strength}</span>
                </p>
              ))}
            </div>
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
                studentId={studentId}
                targetType="essay_draft"
                targetId={firstDraftId}
              />
            ) : null}
          </section>
        ) : null}

        <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
          <form className="space-y-4" onSubmit={handleRevisionSubmit}>
            <label className="block font-semibold">
              二稿
              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                value={revision}
                onChange={(event) => setRevision(event.target.value)}
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
              提交二稿
            </button>
          </form>
        </section>

        {comparison ? (
          <section
            aria-label="二稿对比"
            className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
          >
            <h2 className="text-xl font-bold">二稿对比</h2>
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
                  studentId={studentId}
                  targetType="essay_revision"
                  targetId={revisionResultId}
                />
              </div>
            ) : null}
          </section>
        ) : null}
        {settlement ? <SettlementPanel settlement={settlement} /> : null}
        {isFeedbackPending ? (
          <p role="status">AI 教练正在读你的初稿</p>
        ) : null}
        {isRevisionPending ? (
          <p role="status">AI 教练正在比较两次作文</p>
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
