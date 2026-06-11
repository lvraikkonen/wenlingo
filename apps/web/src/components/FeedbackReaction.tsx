"use client";

import { useEffect, useRef, useState } from "react";
import { saveFeedbackReaction } from "../lib/api";
import { getStoredAlphaSessionId } from "../lib/alphaSession";
import type {
  FeedbackReactionTargetType,
  FeedbackReactionValue,
} from "../lib/types";

const OPTIONS = [
  { value: "positive", label: "😊", aria: "有帮助" },
  { value: "neutral", label: "😐", aria: "一般" },
  { value: "negative", label: "😞", aria: "没帮助" },
] as const;

type FeedbackReactionProps = {
  studentId: string;
  targetType: FeedbackReactionTargetType;
  targetId: string;
  initialReaction?: FeedbackReactionValue | null;
};

export function FeedbackReaction({
  studentId,
  targetType,
  targetId,
  initialReaction = null,
}: FeedbackReactionProps) {
  const reactionKey = `${studentId}:${targetType}:${targetId}:${
    initialReaction ?? "none"
  }`;

  return (
    <FeedbackReactionContent
      key={reactionKey}
      studentId={studentId}
      targetType={targetType}
      targetId={targetId}
      initialReaction={initialReaction}
    />
  );
}

function FeedbackReactionContent({
  studentId,
  targetType,
  targetId,
  initialReaction = null,
}: FeedbackReactionProps) {
  const targetKey = `${studentId}:${targetType}:${targetId}`;
  const activeTargetKey = useRef(targetKey);
  const [selected, setSelected] = useState<FeedbackReactionValue | null>(
    initialReaction,
  );
  const [lastConfirmedReaction, setLastConfirmedReaction] =
    useState<FeedbackReactionValue | null>(initialReaction);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    return () => {
      activeTargetKey.current = "";
    };
  }, []);

  async function handleClick(reaction: FeedbackReactionValue) {
    if (isSaving) {
      return;
    }

    setSelected(reaction);
    setError("");
    setIsSaving(true);
    const saveTargetKey = targetKey;

    try {
      const response = await saveFeedbackReaction(studentId, {
        target_type: targetType,
        target_id: targetId,
        reaction,
        alpha_session_id: getStoredAlphaSessionId(),
      });
      if (activeTargetKey.current !== saveTargetKey) {
        return;
      }
      setLastConfirmedReaction(response.reaction.reaction);
    } catch {
      if (activeTargetKey.current !== saveTargetKey) {
        return;
      }
      setSelected(lastConfirmedReaction);
      setError("这次没有保存成功，稍后可以再点一次。");
    } finally {
      if (activeTargetKey.current === saveTargetKey) {
        setIsSaving(false);
      }
    }
  }

  return (
    <section
      aria-label="AI 教练反馈评价"
      className="rounded-lg border border-[var(--wen-border)] bg-white p-4"
    >
      <p className="text-sm font-semibold">这次 AI 教练的提示对你有帮助吗？</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-label={option.aria}
            aria-pressed={selected === option.value}
            disabled={isSaving}
            onClick={() => handleClick(option.value)}
            className={`inline-flex h-11 w-11 items-center justify-center rounded-lg border text-xl transition disabled:cursor-not-allowed disabled:opacity-60 ${
              selected === option.value
                ? "border-[var(--wen-orange)] bg-[var(--wen-orange-soft)]"
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
