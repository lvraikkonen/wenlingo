"use client";

import type { LegacyOutlineSlot, WritingOutlineSection } from "../../lib/types";

const sectionLabels: Record<LegacyOutlineSlot, string> = {
  cause: "起因",
  process: "经过",
  result: "结果",
  reflection: "感受",
};

function sectionLabel(section: WritingOutlineSection): string {
  return (
    sectionLabels[section.slot as LegacyOutlineSlot] ||
    section.heading ||
    section.slot
  );
}

export function OutlineStep({
  sections,
  onSectionsChange,
  onContinue,
  onDirectWrite,
}: {
  sections: WritingOutlineSection[];
  onSectionsChange: (sections: WritingOutlineSection[]) => void;
  onContinue: () => void;
  onDirectWrite: () => void;
}) {
  function updateSection(sectionId: string, note: string) {
    onSectionsChange(
      sections.map((section) =>
        section.id === sectionId
          ? { ...section, note, child_edited: true, placeholder: false }
          : section,
      ),
    );
  }

  return (
    <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <p className="text-sm font-bold text-[var(--wen-muted)]">
        第 4 步 / 共 4 步：搭一个提纲
      </p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {sections.map((section) => (
          <label key={section.id} className="block font-semibold">
            {sectionLabel(section)}
            <textarea
              className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
              value={section.note}
              onChange={(event) => updateSection(section.id, event.target.value)}
              placeholder={section.heading}
            />
          </label>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
          type="button"
          onClick={onContinue}
        >
          确认提纲，开始写
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
