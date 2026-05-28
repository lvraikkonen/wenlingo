"use client";

import { useState } from "react";
import { saveParentSummaryFeedback } from "../lib/api";
import { getStoredAlphaSessionId } from "../lib/alphaSession";
import type { ParentSummaryUsefulness } from "../lib/types";

const OPTIONS = [
  { value: "helpful", label: "有帮助" },
  { value: "not_helpful", label: "没帮助" },
] as const;

type ParentSummaryFeedbackProps = {
  parentId: string;
  studentId: string;
};

export function ParentSummaryFeedback({
  parentId,
  studentId,
}: ParentSummaryFeedbackProps) {
  const [selected, setSelected] = useState<ParentSummaryUsefulness | null>(null);
  const [error, setError] = useState("");

  async function handleClick(usefulness: ParentSummaryUsefulness) {
    setSelected(usefulness);
    setError("");

    try {
      await saveParentSummaryFeedback(parentId, studentId, {
        usefulness,
        alpha_session_id: getStoredAlphaSessionId(),
      });
    } catch {
      setError("反馈没有保存成功，请稍后再试。");
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
            onClick={() => handleClick(option.value)}
            className={`rounded-lg border px-4 py-2 text-sm font-bold transition ${
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
        <p className="mt-3 text-sm font-semibold text-[var(--wen-muted)]">
          {error}
        </p>
      ) : null}
    </section>
  );
}
