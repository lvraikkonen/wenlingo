"use client";

import { BookOpenText, PenLine } from "lucide-react";

type WritingCastleMode = "classroom" | "direct";

export function WritingCastleModeShell({
  mode,
  onModeChange,
}: {
  mode: WritingCastleMode;
  onModeChange: (mode: WritingCastleMode) => void;
}) {
  const modeClass = (targetMode: WritingCastleMode) =>
    mode === targetMode
      ? "border-[var(--wen-orange)] bg-[var(--wen-bg)]"
      : "border-[var(--wen-border)] bg-white";

  return (
    <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-bold">作文城堡</h1>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <button
          type="button"
          aria-pressed={mode === "classroom"}
          className={`rounded-lg border p-4 text-left font-semibold ${modeClass(
            "classroom",
          )}`}
          onClick={() => onModeChange("classroom")}
        >
          <BookOpenText size={20} aria-hidden="true" />
          <span className="mt-2 block">课内同步作文</span>
        </button>
        <button
          type="button"
          className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-4 text-left font-semibold text-[var(--wen-muted)] disabled:opacity-70"
          disabled
        >
          AI 出题作文 · 稍后开放
        </button>
        <button
          type="button"
          aria-pressed={mode === "direct"}
          className={`rounded-lg border p-4 text-left font-semibold ${modeClass(
            "direct",
          )}`}
          onClick={() => onModeChange("direct")}
        >
          <PenLine size={20} aria-hidden="true" />
          <span className="mt-2 block">直接写初稿</span>
        </button>
      </div>
    </section>
  );
}
