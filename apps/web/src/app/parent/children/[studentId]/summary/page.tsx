"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { ParentSummaryFeedback } from "../../../../../components/ParentSummaryFeedback";
import {
  getMyAlphaChildSummary,
  isUnauthorizedError,
  recordAlphaEvent,
} from "../../../../../lib/api";
import { getStoredAlphaSessionId } from "../../../../../lib/alphaSession";
import type {
  AlphaChildSummary,
  ScaffoldSelectionSource,
} from "../../../../../lib/types";

type SummaryPageProps = {
  params: Promise<{ studentId: string }>;
};

type WritingCastleSummary = NonNullable<AlphaChildSummary["writing_castle_summary"]>;

const selectionSourceLabels: Record<ScaffoldSelectionSource, string> = {
  manual: "孩子手动选择",
  ai_suggested: "AI 建议后确认",
  fallback: "孩子选择相近类型",
};

const materialSourceCategoryLabels: Record<
  NonNullable<WritingCastleSummary["material_source_categories"]>[number],
  string
> = {
  real_experience: "真实经历",
  imagined_setting: "想象设定",
  topic_requirement: "题目要求",
  observation: "观察记录",
  reading_material: "阅读资料",
  child_confirmed: "孩子确认",
};

export default function ParentChildSummaryPage({ params }: SummaryPageProps) {
  const { studentId } = use(params);

  return <ParentChildSummaryPageContent key={studentId} studentId={studentId} />;
}

function ParentChildSummaryPageContent({ studentId }: { studentId: string }) {
  const { replace } = useRouter();
  const [data, setData] = useState<AlphaChildSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;
    getMyAlphaChildSummary(studentId)
      .then((response) => {
        if (isMounted) {
          setData(response);
          recordAlphaEvent({
            event_type: "summary_viewed",
            parent_id: response.parent_id,
            student_id: studentId,
            alpha_session_id: getStoredAlphaSessionId(),
            payload: {
              path: `/parent/children/${studentId}/summary`,
              status: "viewed",
            },
          });
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          if (isUnauthorizedError(error)) {
            replace("/alpha/start");
          } else {
            setError("成长摘要加载失败，请稍后再试。");
          }
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
  }, [replace, studentId]);

  const childName = data?.child.name || data?.child.nickname || "孩子";
  const emptyText =
    data?.empty_state ??
    "还没有训练记录。完成入门小试炼后，这里会出现第一份成长摘要。";
  const hasSentencePractice =
    (data?.practice_counts.sentence_trainings ?? 0) > 0 ||
    Boolean(data?.sentence_training_summary);
  const writingCastleSummary = data?.writing_castle_summary;
  const topicTypeLabel = writingCastleSummary?.selected_topic_type
    ? writingCastleSummary.selected_topic_type_parent &&
      writingCastleSummary.selected_topic_type_parent !==
        writingCastleSummary.selected_topic_type
      ? `${writingCastleSummary.selected_topic_type}（${writingCastleSummary.selected_topic_type_parent}）`
      : writingCastleSummary.selected_topic_type
    : "";
  const selectionSourceLabel = writingCastleSummary?.selection_source
    ? selectionSourceLabels[writingCastleSummary.selection_source]
    : "";
  const materialSourceLabel = writingCastleSummary?.material_source_categories
    ?.map((category) => materialSourceCategoryLabels[category])
    .filter(Boolean)
    .join("、");

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
          <nav
            aria-label="成长摘要导航"
            className="flex flex-wrap gap-3 text-sm font-bold"
          >
            {data?.child.dashboard_url ? (
              <Link
                href={data.child.dashboard_url}
                className="inline-flex w-fit rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white"
              >
                回到孩子空间
              </Link>
            ) : null}
            <Link
              href="/parent/children"
              className="inline-flex w-fit rounded-lg border border-[var(--wen-border)] px-5 py-3 font-semibold"
            >
              返回孩子列表
            </Link>
          </nav>
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
                    {data.sentence_training_summary ? (
                      <p className="mt-2 text-sm text-[var(--wen-muted)]">
                        {data.sentence_training_summary}
                      </p>
                    ) : null}
                    {hasSentencePractice ? (
                      <p className="mt-2 text-sm font-semibold text-[var(--wen-orange)]">
                        本周{childName}完成了{" "}
                        {data.practice_counts.sentence_trainings}{" "}
                        次练习，主要在练把句子写具体。
                      </p>
                    ) : null}
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

                {data.writing_castle_summary ? (
                  <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
                    <h2 className="text-xl font-bold">作文构思过程</h2>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                        题目：{data.writing_castle_summary.topic}
                      </p>
                      {topicTypeLabel ? (
                        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                          作文类型：{topicTypeLabel}
                        </p>
                      ) : null}
                      {selectionSourceLabel ? (
                        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                          选择方式：{selectionSourceLabel}
                        </p>
                      ) : null}
                      {materialSourceLabel ? (
                        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                          素材来源：{materialSourceLabel}
                        </p>
                      ) : null}
                      {data.writing_castle_summary
                        .unsupported_future_type_overridden ? (
                        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                          题型覆盖：孩子选择了相近的已支持类型
                        </p>
                      ) : null}
                      {data.writing_castle_summary.copy_ready_ai_body_generated ===
                      false ? (
                        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                          AI 正文：没有生成可直接照抄的作文正文
                        </p>
                      ) : null}
                      <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                        审题：
                        {data.writing_castle_summary.topic_analysis_used
                          ? "已使用"
                          : "已跳过"}
                      </p>
                      <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                        选材：回答{" "}
                        {data.writing_castle_summary.material_questions_answered}{" "}
                        个问题
                      </p>
                      <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                        素材卡：保留{" "}
                        {data.writing_castle_summary.material_cards_retained} 张
                      </p>
                      <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                        提纲：
                        {data.writing_castle_summary.outline_confirmed
                          ? data.writing_castle_summary.outline_edited
                            ? "已确认并修改"
                            : "已确认"
                          : "未确认"}
                      </p>
                      <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
                        初稿：
                        {data.writing_castle_summary.first_draft_completed
                          ? "已完成"
                          : "未完成"}
                      </p>
                    </div>
                  </section>
                ) : null}

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
            {data.parent_id ? (
              <ParentSummaryFeedback
                key={`${data.parent_id}:${studentId}`}
                parentId={data.parent_id}
                studentId={studentId}
                initialUsefulness={data.usefulness ?? null}
              />
            ) : null}
          </div>
        ) : null}
      </section>
    </main>
  );
}
