import { createReport } from "../../../../lib/api";

export default async function ReportPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;
  const report = await createReport(studentId);

  return (
    <section aria-label="阶段报告">
      <h1>阶段报告</h1>
      <p>{report.content.practice_summary}</p>
      {report.content.ability_changes.map((change) => (
        <p key={change}>{change}</p>
      ))}
      <p>{report.content.best_revision}</p>
      {report.content.weak_points.map((weakPoint) => (
        <p key={weakPoint}>{weakPoint}</p>
      ))}
      {report.content.next_suggestions.map((suggestion: string) => (
        <p key={suggestion}>{suggestion}</p>
      ))}
    </section>
  );
}
