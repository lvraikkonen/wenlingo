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
    <main>
      <h1>{dashboard.student.name}的小文星球</h1>
      <p>{dashboard.ability_note}</p>
      <TaskCards
        main={dashboard.today_tasks.main}
        quick={dashboard.today_tasks.quick}
      />
      <PlanetMap places={dashboard.map} />
      <AiCoachPanel message={dashboard.coach_message} />
      <AbilityBars abilities={dashboard.child_abilities} />
    </main>
  );
}
