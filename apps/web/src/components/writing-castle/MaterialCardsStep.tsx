"use client";

import type { MaterialCardSlot } from "../../lib/types";

const cardLabels: Record<MaterialCardSlot["category"], string> = {
  event: "事件",
  detail: "细节",
  feeling_takeaway: "心情收获",
};

export function MaterialCardsStep({
  cards,
  onCardsChange,
  onContinue,
  onDirectWrite,
}: {
  cards: MaterialCardSlot[];
  onCardsChange: (cards: MaterialCardSlot[]) => void;
  onContinue: () => void;
  onDirectWrite: () => void;
}) {
  const visibleCards = cards.filter((card) => !card.deleted);

  function updateCard(cardId: string, text: string) {
    onCardsChange(
      cards.map((card) =>
        card.id === cardId
          ? { ...card, text, child_edited: true, placeholder: false }
          : card,
      ),
    );
  }

  function moveCard(cardId: string, direction: -1 | 1) {
    const currentIndex = visibleCards.findIndex((card) => card.id === cardId);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= visibleCards.length) {
      return;
    }

    const reordered = [...visibleCards];
    const [moved] = reordered.splice(currentIndex, 1);
    reordered.splice(targetIndex, 0, moved);
    const orderById = new Map(
      reordered.map((card, index) => [card.id, index + 1] as const),
    );

    onCardsChange(
      cards.map((card) =>
        orderById.has(card.id) ? { ...card, order: orderById.get(card.id)! } : card,
      ),
    );
  }

  function deleteCard(cardId: string) {
    onCardsChange(
      cards.map((card) =>
        card.id === cardId ? { ...card, deleted: true, child_edited: true } : card,
      ),
    );
  }

  return (
    <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <p className="text-sm font-bold text-[var(--wen-muted)]">
        第 3 步 / 共 4 步：整理素材卡
      </p>
      <div className="mt-5 space-y-4">
        {visibleCards
          .slice()
          .sort((left, right) => left.order - right.order)
          .map((card, index) => (
            <div
              key={card.id}
              className="rounded-lg border border-[var(--wen-border)] p-4"
            >
              <label className="block font-semibold">
                {cardLabels[card.category]}
                <textarea
                  className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                  value={card.text}
                  onChange={(event) => updateCard(card.id, event.target.value)}
                />
              </label>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="rounded-lg border border-[var(--wen-border)] px-3 py-2 text-sm font-semibold disabled:opacity-50"
                  type="button"
                  disabled={index === 0}
                  onClick={() => moveCard(card.id, -1)}
                >
                  上移
                </button>
                <button
                  className="rounded-lg border border-[var(--wen-border)] px-3 py-2 text-sm font-semibold disabled:opacity-50"
                  type="button"
                  disabled={index === visibleCards.length - 1}
                  onClick={() => moveCard(card.id, 1)}
                >
                  下移
                </button>
                <button
                  className="rounded-lg border border-[var(--wen-border)] px-3 py-2 text-sm font-semibold"
                  type="button"
                  onClick={() => deleteCard(card.id)}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
          type="button"
          onClick={onContinue}
        >
          生成提纲
        </button>
        <button
          className="rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
          type="button"
          onClick={onDirectWrite}
        >
          我想直接开始写
        </button>
      </div>
    </section>
  );
}
