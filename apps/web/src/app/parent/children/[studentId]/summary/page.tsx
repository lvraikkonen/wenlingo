"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { getAlphaChildSummary } from "../../../../../lib/api";
import { getStoredAlphaParentId } from "../../../../../lib/alphaParent";
import type { AlphaChildSummary } from "../../../../../lib/types";

type SummaryPageProps = {
  params: Promise<{ studentId: string }>;
};

export default function ParentChildSummaryPage({ params }: SummaryPageProps) {
  const { studentId } = use(params);
  const router = useRouter();
  const [data, setData] = useState<AlphaChildSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const parentId = getStoredAlphaParentId();
    if (!parentId) {
      router.replace("/alpha/start");
      return;
    }

    let isMounted = true;
    getAlphaChildSummary(parentId, studentId)
      .then((response) => {
        if (isMounted) {
          setData(response);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("成长摘要加载失败，请稍后再试。");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [router, studentId]);

  const childName = data?.child.name || data?.child.nickname || "孩子";
  const emptyText =
    data?.empty_state ??
    "还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。";

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-4xl">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-[var(--wen-muted)]">
              Growth Summary
            </p>
            <h1 className="mt-2 text-3xl font-bold">{childName}的成长摘要</h1>
            {data?.child.grade_label ? (
              <p className="mt-2 text-[var(--wen-muted)]">
                {data.child.grade_label} ·{" "}
                {data.assessment_completed ? "已完成入门小试炼" : "等待入门小试炼"}
              </p>
            ) : null}
          </div>
          {data?.child.dashboard_url ? (
            <Link
              href={data.child.dashboard_url}
              className="inline-flex w-fit rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white"
            >
              进入孩子空间
            </Link>
          ) : null}
        </div>

        {isLoading ? (
          <p
            role="status"
            aria-live="polite"
            className="mt-8 rounded-lg border border-[var(--wen-border)] bg-white p-5 text-[var(--wen-muted)]"
          >
            正在加载成长摘要...
          </p>
        ) : null}

        {error ? (
          <p
            role="alert"
            className="mt-8 rounded-lg border border-red-200 bg-red-50 p-5 font-semibold text-red-700"
          >
            {error}
          </p>
        ) : null}

        {!isLoading && !error && data ? (
          <div className="mt-8 space-y-5">
            {data.empty_state ? (
              <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
                <p className="font-semibold">{emptyText}</p>
                <p className="mt-3 text-[var(--wen-muted)]">
                  {data.next_suggestion}
                </p>
              </section>
            ) : (
              <>
                <section className="grid gap-4 sm:grid-cols-3">
                  <div className="rounded-lg border border-[var(--wen-border)] bg-white p-5 shadow-sm">
                    <p className="text-sm font-semibold text-[var(--wen-muted)]">
                      入门小试炼
                    </p>
                    <p className="mt-2 text-xl font-bold">
                      入门小试炼 {data.practice_counts.assessments} 次
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--wen-border)] bg-white p-5 shadow-sm">
                    <p className="text-sm font-semibold text-[var(--wen-muted)]">
                      句子训练
                    </p>
                    <p className="mt-2 text-xl font-bold">
                      句子训练 {data.practice_counts.sentence_trainings} 次
                    </p>
                  </div>
                  <div className="rounded-lg border border-[var(--wen-border)] bg-white p-5 shadow-sm">
                    <p className="text-sm font-semibold text-[var(--wen-muted)]">
                      小写作
                    </p>
                    <p className="mt-2 text-xl font-bold">
                      小写作 {data.practice_counts.essays} 次
                    </p>
                  </div>
                </section>

                <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
                  <h2 className="text-xl font-bold">能力变化</h2>
                  <div className="mt-4 flex flex-wrap gap-3">
                    {data.ability_changes.map((change) => (
                      <span
                        key={change.ability}
                        className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold"
                      >
                        {change.label} {change.delta >= 0 ? "+" : ""}
                        {change.delta}
                      </span>
                    ))}
                  </div>
                </section>

                <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
                  <h2 className="text-xl font-bold">最近亮点</h2>
                  {data.recent_highlight ? (
                    <p className="mt-3 text-[var(--wen-muted)]">
                      {data.recent_highlight}
                    </p>
                  ) : null}
                  <h2 className="mt-6 text-xl font-bold">下一步建议</h2>
                  <p className="mt-3 text-[var(--wen-muted)]">
                    {data.next_suggestion}
                  </p>
                </section>
              </>
            )}
          </div>
        ) : null}
      </section>
    </main>
  );
}
