import { createReport } from "../../../../lib/api";

export default async function ReportPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;
  const report = await createReport(studentId);

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <section
        aria-label="阶段报告"
        className="mx-auto max-w-3xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
      >
        <h1 className="text-2xl font-bold">阶段报告</h1>
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
      </section>
    </main>
  );
}
