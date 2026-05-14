import { AbilityBars } from "../../../components/AbilityBars";
import { AiCoachPanel } from "../../../components/AiCoachPanel";
import { PlanetMap } from "../../../components/PlanetMap";
import { TaskCards } from "../../../components/TaskCards";
import { getDashboard } from "../../../lib/api";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;
  const dashboard = await getDashboard(studentId);

  return (
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
        <PlanetMap places={dashboard.map} />
        <AiCoachPanel message={dashboard.coach_message} />
        <AbilityBars abilities={dashboard.child_abilities} />
      </div>
    </main>
  );
}
