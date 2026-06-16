import { DashboardViewedEvent } from "../../../components/DashboardViewedEvent";
import { DashboardClient } from "./DashboardClient";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = await params;

  return (
    <>
      <DashboardViewedEvent studentId={studentId} />
      <DashboardClient studentId={studentId} />
    </>
  );
}
