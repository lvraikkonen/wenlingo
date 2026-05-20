"use client";

import Link from "next/link";
import { use, useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { FamilyTopbar } from "../../../../components/FamilyTopbar";
import { SettlementPanel } from "../../../../components/SettlementPanel";
import {
  createSentenceTraining,
  type SentenceFocus,
  type SentenceTrainingResponse,
} from "../../../../lib/api";

const DEFAULT_SENTENCE_FOCUS: SentenceFocus = "加细节";

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
    setResult(null);

    try {
      const result = await createSentenceTraining(studentId, {
        source_sentence: sourceSentence,
        upgraded_sentence: upgradedSentence,
        focus: DEFAULT_SENTENCE_FOCUS,
      });

      setResult(result);
    } catch {
      setError("这次句子练习没有提交成功。先别急，检查一下网络后再试一次。");
    } finally {
      setIsSubmitting(false);
    }
  }

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

          <form className="space-y-5" onSubmit={handleSubmit}>
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

          {isSubmitting ? (
            <p
              className="mt-4 rounded-lg bg-[var(--wen-bg)] px-4 py-3 text-sm font-semibold text-[var(--wen-orange)]"
              role="status"
            >
              AI 教练正在看你的句子
            </p>
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
              <section
                aria-label="AI 教练反馈"
                className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-5"
              >
                <h2 className="text-xl font-bold">AI 教练反馈</h2>
                <p className="mt-3 text-base font-semibold">
                  {result.feedback.encouragement}
                </p>
                <p className="mt-2 text-sm text-[var(--wen-muted)]">
                  {result.feedback.specific_improvement}
                </p>

                <h3 className="mt-5 text-sm font-bold">发现的问题怪兽</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {result.feedback.problem_monsters.map((monster) => (
                    <span
                      className="rounded-lg bg-white px-3 py-1 text-sm font-semibold text-[var(--wen-orange)]"
                      key={monster}
                    >
                      {monster}
                    </span>
                  ))}
                </div>

                <h3 className="mt-5 text-sm font-bold">下一小步</h3>
                <p className="mt-2 text-sm">{result.feedback.next_step}</p>
              </section>
              <SettlementPanel settlement={result.settlement} />
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
              </nav>
            </div>
          ) : null}
        </div>
      </main>
    </>
  );
}
