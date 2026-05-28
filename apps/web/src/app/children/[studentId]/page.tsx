import Script from "next/script";
import { AbilityBars } from "../../../components/AbilityBars";
import { AiCoachPanel } from "../../../components/AiCoachPanel";
import { FamilyTopbar } from "../../../components/FamilyTopbar";
import { PlanetMap } from "../../../components/PlanetMap";
import { TaskCards } from "../../../components/TaskCards";
import { getDashboard } from "../../../lib/api";

function AlphaDashboardViewedScript({ studentId }: { studentId: string }) {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const script = `
(() => {
  try {
    const parentId = window.localStorage.getItem("wenlingo_alpha_parent_id");
    if (!parentId) {
      return;
    }
    const alphaSessionId = window.localStorage.getItem("wenlingo_alpha_session_id") || "";
    window.fetch(${JSON.stringify(`${apiBaseUrl}/api/alpha/events`)}, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: "child_dashboard_viewed",
        parent_id: parentId,
        student_id: ${JSON.stringify(studentId)},
        alpha_session_id: alphaSessionId,
        payload: {
          path: ${JSON.stringify(`/children/${studentId}`)},
          status: "viewed",
        },
      }),
      cache: "no-store",
    }).catch(() => undefined);
  } catch {
  }
})();
`;

  return (
    <Script
      id={`alpha-child-dashboard-viewed-${studentId}`}
      strategy="afterInteractive"
      dangerouslySetInnerHTML={{ __html: script }}
    />
  );
}

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;
  const dashboard = await getDashboard(studentId);

  return (
    <>
      <AlphaDashboardViewedScript studentId={studentId} />
      <FamilyTopbar currentStudentId={studentId} />
      <main className="min-h-screen px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
          <h1 className="text-2xl font-bold">
            {dashboard.student.name}的小文星球
          </h1>
          <p className="mt-2 text-[var(--wen-muted)]">
            {dashboard.ability_note}
          </p>
        </section>
        <TaskCards
          studentId={studentId}
          main={dashboard.today_tasks.main}
          quick={dashboard.today_tasks.quick}
        />
        <PlanetMap studentId={studentId} places={dashboard.map} />
        <AiCoachPanel message={dashboard.coach_message} />
        <AbilityBars abilities={dashboard.child_abilities} />
      </div>
      </main>
    </>
  );
}
