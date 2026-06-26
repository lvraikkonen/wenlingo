"use client";

import type {
  LegacyMaterialCardCategory,
  MaterialCardSlot,
  WritingOutlineSection,
} from "../../lib/types";

const cardLabels: Record<LegacyMaterialCardCategory, string> = {
  event: "事件",
  detail: "细节",
  feeling_takeaway: "心情收获",
};

function cardLabel(category: MaterialCardSlot["category"]): string {
  return cardLabels[category as LegacyMaterialCardCategory] ?? category;
}

export function FirstDraftStep({
  cards,
  sections,
  draft,
  onDraftChange,
  onSubmit,
  isPending = false,
}: {
  cards: MaterialCardSlot[];
  sections: WritingOutlineSection[];
  draft: string;
  onDraftChange: (draft: string) => void;
  onSubmit: () => void;
  isPending?: boolean;
}) {
  const visibleCards = cards.filter(
    (card) => !card.deleted && card.text.trim().length > 0,
  );
  const visibleSections = sections.filter(
    (section) => section.note.trim().length > 0,
  );

  return (
    <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <div className="grid gap-5 lg:grid-cols-[1fr_2fr]">
        <aside className="space-y-4">
          {visibleCards.length > 0 ? (
            <div>
              <h2 className="font-bold">素材提醒</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {visibleCards.map((card) => (
                  <li key={card.id}>
                    <span className="font-semibold">{cardLabel(card.category)}：</span>
                    {card.text}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {visibleSections.length > 0 ? (
            <div>
              <h2 className="font-bold">提纲提醒</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {visibleSections.map((section) => (
                  <li key={section.id}>
                    <span className="font-semibold">{section.heading}：</span>
                    {section.note}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </aside>
        <div>
          <label className="block font-semibold">
            初稿
            <textarea
              className="mt-2 min-h-56 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
            />
          </label>
          <button
            className="mt-4 rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white disabled:opacity-60"
            type="button"
            disabled={isPending}
            onClick={onSubmit}
          >
            提交初稿给 AI 教练
          </button>
        </div>
      </div>
    </section>
  );
}
