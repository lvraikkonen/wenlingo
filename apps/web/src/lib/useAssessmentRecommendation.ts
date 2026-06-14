"use client";

import { useEffect, useState } from "react";
import * as api from "./api";

export function useAssessmentRecommendation(studentId: string) {
  const [isRecommended, setIsRecommended] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  useEffect(() => {
    let active = true;

    queueMicrotask(() => {
      if (active) {
        setIsDismissed(false);
        setIsRecommended(false);
      }
    });

    if (!("getDashboard" in api)) {
      return () => {
        active = false;
      };
    }

    api
      .getDashboard(studentId)
      .then((dashboard) => {
        if (active) {
          setIsRecommended(dashboard.assessment_recommended);
        }
      })
      .catch((error: unknown) => {
        const isUnauthorized =
          "isUnauthorizedError" in api && api.isUnauthorizedError(error);
        if (active && !isUnauthorized) {
          setIsRecommended(false);
        }
      });

    return () => {
      active = false;
    };
  }, [studentId]);

  return {
    shouldShowAssessmentRecommendation: isRecommended && !isDismissed,
    dismissAssessmentRecommendation: () => setIsDismissed(true),
  };
}
