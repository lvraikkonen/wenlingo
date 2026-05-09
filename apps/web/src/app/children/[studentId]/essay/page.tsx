"use client";

import { use, useState } from "react";
import type { FormEvent } from "react";
import { SettlementPanel } from "../../../../components/SettlementPanel";
import {
  createEssay,
  submitEssayRevision,
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
  const [feedback, setFeedback] = useState<null | {
    strengths: string[];
    revision_tasks: { instruction: string; target: string }[];
  }>(null);
  const [comparison, setComparison] = useState<null | {
    encouragement: string;
    improved_dimensions: string[];
  }>(null);
  const [settlement, setSettlement] = useState<Settlement | null>(null);
  const [isFeedbackPending, setIsFeedbackPending] = useState(false);
  const [isRevisionPending, setIsRevisionPending] = useState(false);
  const [error, setError] = useState("");

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
      setFeedback(result.feedback);
      setComparison(null);
      setSettlement(null);
    } catch {
      setError("提交失败，请稍后再试。");
    } finally {
      setIsFeedbackPending(false);
    }
  }

  async function handleRevisionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!essayId) {
      return;
    }

    setIsRevisionPending(true);
    setError("");

    try {
      const result = await submitEssayRevision(essayId, { content: revision });

      setComparison(result.comparison);
      setSettlement(result.settlement);
    } catch {
      setError("提交失败，请稍后再试。");
    } finally {
      setIsRevisionPending(false);
    }
  }

  return (
    <main>
      <h1>作文修改</h1>
      <form onSubmit={handleFeedbackSubmit}>
        <label>
          作文题目
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label>
          初稿
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        </label>
        <button type="submit" disabled={isFeedbackPending}>
          获得点评
        </button>
      </form>

      {feedback ? (
        <section aria-label="作文点评">
          <h2>作文点评</h2>
          {feedback.strengths.map((strength) => (
            <p key={strength}>{strength}</p>
          ))}
          {feedback.revision_tasks.map((task) => (
            <div key={`${task.target}-${task.instruction}`}>
              <p>{task.target}</p>
              <p>{task.instruction}</p>
            </div>
          ))}
        </section>
      ) : null}

      <form onSubmit={handleRevisionSubmit}>
        <label>
          二稿
          <textarea
            value={revision}
            onChange={(event) => setRevision(event.target.value)}
          />
        </label>
        <button type="submit" disabled={!essayId || isRevisionPending}>
          提交二稿
        </button>
      </form>

      {comparison ? (
        <section aria-label="二稿对比">
          <h2>二稿对比</h2>
          <p>{comparison.encouragement}</p>
          {comparison.improved_dimensions.map((dimension) => (
            <p key={dimension}>{dimension}</p>
          ))}
        </section>
      ) : null}
      {settlement ? <SettlementPanel settlement={settlement} /> : null}
      {isFeedbackPending || isRevisionPending ? (
        <p role="status">正在提交...</p>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
