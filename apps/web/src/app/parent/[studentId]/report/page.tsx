"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { FamilyTopbar } from "../../../../components/FamilyTopbar";
import { createReport } from "../../../../lib/api";

type ReportResult = Awaited<ReturnType<typeof createReport>>;
type ReportLoadState = {
  studentId: string;
  report: ReportResult | null;
  isLoading: boolean;
};

export function ReportPageContent({ studentId }: { studentId: string }) {
  const [reportState, setReportState] = useState<ReportLoadState>(() => ({
    studentId,
    report: null,
    isLoading: true,
  }));
  const isCurrentReport = reportState.studentId === studentId;
  const report = isCurrentReport ? reportState.report : null;
  const isLoading = !isCurrentReport || reportState.isLoading;

  useEffect(() => {
    let active = true;

    createReport(studentId)
      .then((result) => {
        if (active) {
          setReportState({ studentId, report: result, isLoading: false });
        }
      })
      .catch(() => {
        if (active) {
          setReportState({ studentId, report: null, isLoading: false });
        }
      });

    return () => {
      active = false;
    };
  }, [studentId]);

  return (
    <>
      <FamilyTopbar currentStudentId={studentId} />
      <main className="min-h-screen px-5 py-8 sm:px-8">
        <section
          aria-label="阶段报告"
          className="mx-auto max-w-3xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
        >
          <h1 className="text-2xl font-bold">阶段报告</h1>
          {isLoading ? (
            <p role="status" className="mt-4 text-[var(--wen-muted)]">
              正在生成阶段报告...
            </p>
          ) : report ? (
            <>
              <p className="mt-4 text-[var(--wen-muted)]">
                {report.content.practice_summary}
              </p>
              <h2 className="mt-6 font-semibold">这次看见的进步</h2>
              {report.content.ability_changes.map((change) => (
                <p className="mt-2" key={change}>
                  {change}
                </p>
              ))}
              <h2 className="mt-6 font-semibold">最有证据的一处修改</h2>
              <p className="mt-2">{report.content.best_revision}</p>
              <h2 className="mt-6 font-semibold">下一步</h2>
              {report.content.weak_points.map((weakPoint) => (
                <p className="mt-2 text-[var(--wen-muted)]" key={weakPoint}>
                  {weakPoint}
                </p>
              ))}
              {report.content.next_suggestions.map((suggestion: string) => (
                <p className="mt-2" key={suggestion}>
                  {suggestion}
                </p>
              ))}
            </>
          ) : (
            <p className="mt-4 text-[var(--wen-muted)]">
              阶段报告暂时无法生成，请稍后再试。
            </p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              className="inline-flex rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
              href={`/children/${studentId}`}
            >
              回到当前孩子 Dashboard
            </Link>
            <Link
              className="inline-flex rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
              href="/parent/children"
            >
              返回孩子列表
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}

export default function ReportPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);

  return <ReportPageContent studentId={studentId} />;
}
