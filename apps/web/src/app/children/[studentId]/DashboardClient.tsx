"use client";

import { useEffect, useState } from "react";
import { AbilityBars } from "../../../components/AbilityBars";
import { AiCoachPanel } from "../../../components/AiCoachPanel";
import { FamilyTopbar } from "../../../components/FamilyTopbar";
import { PlanetMap } from "../../../components/PlanetMap";
import { TaskCards } from "../../../components/TaskCards";
import { getDashboard, isUnauthorizedError } from "../../../lib/api";
import type { DashboardResponse } from "../../../lib/types";
import { useRouter } from "next/navigation";

export function DashboardClient({ studentId }: { studentId: string }) {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setError("");
      try {
        const response = await getDashboard(studentId);
        if (!cancelled) {
          setDashboard(response);
        }
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        if (isUnauthorizedError(loadError)) {
          router.replace("/alpha/start");
          return;
        }
        setError("孩子空间加载失败，请稍后再试。");
      }
    }

    void loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [router, studentId]);

  if (error) {
    return (
      <>
        <FamilyTopbar currentStudentId={studentId} />
        <main className="min-h-screen px-5 py-8 sm:px-8">
          <div className="mx-auto max-w-5xl">
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
              {error}
            </p>
          </div>
        </main>
      </>
    );
  }

  if (!dashboard) {
    return (
      <>
        <FamilyTopbar currentStudentId={studentId} />
        <main className="min-h-screen px-5 py-8 sm:px-8">
          <div className="mx-auto max-w-5xl">
            <p className="text-[var(--wen-muted)]">正在准备小文星球...</p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
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
