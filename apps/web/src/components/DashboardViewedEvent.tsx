"use client";

import { useEffect } from "react";
import { recordAlphaEvent } from "../lib/api";
import { getStoredAlphaSessionId } from "../lib/alphaSession";

export function DashboardViewedEvent({ studentId }: { studentId: string }) {
  useEffect(() => {
    void recordAlphaEvent({
      event_type: "child_dashboard_viewed",
      student_id: studentId,
      alpha_session_id: getStoredAlphaSessionId(),
      payload: {
        path: `/children/${studentId}`,
        status: "viewed",
      },
    });
  }, [studentId]);

  return null;
}
