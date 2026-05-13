"use client";

import { use, useState } from "react";
import type { FormEvent } from "react";
import { createAssessment } from "../../../../lib/api";

export default function AssessmentPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const [sentenceBefore, setSentenceBefore] = useState("");
  const [sentenceAfter, setSentenceAfter] = useState("");
  const [shortWriting, setShortWriting] = useState("");
  const [summary, setSummary] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const result = await createAssessment(studentId, {
        sentence_before: sentenceBefore,
        sentence_after: sentenceAfter,
        short_writing: shortWriting,
      });

      setSummary(result.assessment.summary);
    } catch {
      setError("提交失败，请稍后再试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>入门小试炼</h1>
      <form onSubmit={handleSubmit}>
        <label>
          升级前的句子
          <textarea
            value={sentenceBefore}
            onChange={(event) => setSentenceBefore(event.target.value)}
          />
        </label>
        <label>
          升级后的句子
          <textarea
            value={sentenceAfter}
            onChange={(event) => setSentenceAfter(event.target.value)}
          />
        </label>
        <label>
          小写作
          <textarea
            value={shortWriting}
            onChange={(event) => setShortWriting(event.target.value)}
          />
        </label>
        <button type="submit" disabled={isSubmitting}>
          完成小试炼
        </button>
      </form>
      {isSubmitting ? <p role="status">正在提交...</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {summary ? <p>{summary}</p> : null}
    </main>
  );
}
