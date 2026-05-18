"use client";

import { use, useState } from "react";
import type { FormEvent } from "react";
import { FamilyTopbar } from "../../../../components/FamilyTopbar";
import { SettlementPanel } from "../../../../components/SettlementPanel";
import {
  createSentenceTraining,
  type SentenceTrainingResponse,
} from "../../../../lib/api";

export default function SentencePage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const [sourceSentence, setSourceSentence] = useState("");
  const [upgradedSentence, setUpgradedSentence] = useState("");
  const [result, setResult] = useState<SentenceTrainingResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const result = await createSentenceTraining(studentId, {
        source_sentence: sourceSentence,
        upgraded_sentence: upgradedSentence,
        focus: "加细节",
      });

      setResult(result);
    } catch {
      setError("提交失败，请稍后再试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <main>
      <h1>句子工坊</h1>
      <form onSubmit={handleSubmit}>
        <label>
          原句
          <textarea
            value={sourceSentence}
            onChange={(event) => setSourceSentence(event.target.value)}
          />
        </label>
        <label>
          升级后的句子
          <textarea
            value={upgradedSentence}
            onChange={(event) => setUpgradedSentence(event.target.value)}
          />
        </label>
        <button type="submit" disabled={isSubmitting}>
          提交给 AI 教练
        </button>
      </form>
      {isSubmitting ? <p role="status">正在提交...</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {result ? (
        <>
          <section aria-label="AI 教练反馈">
            <h2>AI 教练反馈</h2>
            <p>{result.feedback.encouragement}</p>
            <p>{result.feedback.specific_improvement}</p>
          </section>
          <SettlementPanel settlement={result.settlement} />
        </>
      ) : null}
      </main>
    </>
  );
}
