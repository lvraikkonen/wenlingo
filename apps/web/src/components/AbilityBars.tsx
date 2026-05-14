const labels = {
  reading_power: "读懂力",
  specific_writing_power: "写具体力",
  revision_power: "会修改力",
} as const;

type AbilityKey = keyof typeof labels;

export function AbilityBars({
  abilities,
}: {
  abilities: Record<AbilityKey, number>;
}) {
  return (
    <section
      aria-label="能力画像"
      className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
    >
      <h2 className="text-xl font-bold">能力画像</h2>
      <div className="mt-4 space-y-4">
        {Object.entries(labels).map(([key, label]) => (
          <div key={key} className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold">{label}</span>
              <span className="text-sm text-[var(--wen-muted)]">
                {abilities[key as AbilityKey]} / 100
              </span>
            </div>
            <progress
              aria-label={label}
              className="h-3 w-full"
              value={abilities[key as AbilityKey]}
              max={100}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
