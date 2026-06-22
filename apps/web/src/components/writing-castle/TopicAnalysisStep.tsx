"use client";

import type { TopicAnalysisCard } from "../../lib/types";

export function TopicAnalysisStep({
  cards,
  focus,
  onFocusChange,
  onContinue,
  onSkip,
}: {
  cards: TopicAnalysisCard[];
  focus: string;
  onFocusChange: (value: string) => void;
  onContinue: () => void;
  onSkip: () => void;
}) {
  return (
    <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <p className="text-sm font-bold text-[var(--wen-muted)]">
        第 1 步 / 共 4 步：看懂题目
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {cards.map((card) => (
          <article
            key={card.id}
            className="rounded-lg border border-[var(--wen-border)] p-4"
          >
            <h2 className="font-bold">{card.title}</h2>
            <p className="mt-2 text-sm text-[var(--wen-muted)]">{card.body}</p>
            {card.required_points.length > 0 ? (
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
                {card.required_points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </div>
      <label className="mt-5 block font-semibold">
        我觉得这题最重要的是
        <textarea
          className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
          value={focus}
          onChange={(event) => onFocusChange(event.target.value)}
          placeholder="写一句就可以"
        />
      </label>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
          type="button"
          onClick={onContinue}
        >
          继续想素材
        </button>
        <button
          className="rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
          type="button"
          onClick={onSkip}
        >
          先跳过，我想继续
        </button>
      </div>
    </section>
  );
}
