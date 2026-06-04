import Script from "next/script";
import { buildAlphaDashboardViewedScript } from "../../../lib/alphaSession";
import { DashboardClient } from "./DashboardClient";

function AlphaDashboardViewedScript({ studentId }: { studentId: string }) {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const script = buildAlphaDashboardViewedScript({ studentId, apiBaseUrl });

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

  return (
    <>
      <AlphaDashboardViewedScript studentId={studentId} />
      <DashboardClient studentId={studentId} />
    </>
  );
}
