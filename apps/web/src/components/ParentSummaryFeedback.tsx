"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { isUnauthorizedError, saveMyParentSummaryFeedback } from "../lib/api";
import { getStoredAlphaSessionId } from "../lib/alphaSession";
import type { ParentSummaryUsefulness } from "../lib/types";

const OPTIONS = [
  { value: "helpful", label: "有帮助" },
  { value: "not_helpful", label: "没帮助" },
] as const;

type ParentSummaryFeedbackProps = {
  parentId: string;
  studentId: string;
  initialUsefulness?: ParentSummaryUsefulness | null;
};

export function ParentSummaryFeedback({
  parentId,
  studentId,
  initialUsefulness = null,
}: ParentSummaryFeedbackProps) {
  const router = useRouter();
  const targetKey = `${parentId}:${studentId}`;
  const activeTargetKey = useRef(targetKey);
  const [selected, setSelected] = useState<ParentSummaryUsefulness | null>(
    initialUsefulness,
  );
  const [lastConfirmedUsefulness, setLastConfirmedUsefulness] =
    useState<ParentSummaryUsefulness | null>(initialUsefulness);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    activeTargetKey.current = targetKey;
    setSelected(initialUsefulness);
    setLastConfirmedUsefulness(initialUsefulness);
    setIsSaving(false);
    setError("");
  }, [initialUsefulness, parentId, studentId, targetKey]);

  async function handleClick(usefulness: ParentSummaryUsefulness) {
    if (isSaving) {
      return;
    }

    setSelected(usefulness);
    setError("");
    setIsSaving(true);
    const saveTargetKey = targetKey;

    try {
      const response = await saveMyParentSummaryFeedback(studentId, {
        usefulness,
        alpha_session_id: getStoredAlphaSessionId(),
      });
      if (activeTargetKey.current !== saveTargetKey) {
        return;
      }
      setLastConfirmedUsefulness(response.feedback.usefulness);
    } catch (requestError: unknown) {
      if (activeTargetKey.current !== saveTargetKey) {
        return;
      }
      if (isUnauthorizedError(requestError)) {
        router.replace("/alpha/start");
        return;
      }
      setSelected(lastConfirmedUsefulness);
      setError("反馈没有保存成功，请稍后再试。");
    } finally {
      if (activeTargetKey.current === saveTargetKey) {
        setIsSaving(false);
      }
    }
  }

  return (
    <section
      aria-label="成长摘要反馈"
      className="rounded-lg border border-[var(--wen-border)] bg-white p-5 shadow-sm"
    >
      <p className="font-semibold">这份成长摘要对你有帮助吗？</p>
      <div className="mt-3 flex flex-wrap gap-3">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected === option.value}
            disabled={isSaving}
            onClick={() => handleClick(option.value)}
            className={`rounded-lg border px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-60 ${
              selected === option.value
                ? "border-[var(--wen-orange)] bg-[var(--wen-orange-soft)] text-[var(--wen-orange)]"
                : "border-[var(--wen-border)] bg-white"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      {error ? (
        <p
          role="alert"
          className="mt-3 text-sm font-semibold text-[var(--wen-muted)]"
        >
          {error}
        </p>
      ) : null}
    </section>
  );
}
