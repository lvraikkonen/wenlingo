const labels = {
  reading_power: "读懂力",
  specific_writing_power: "写具体力",
  revision_power: "会修改力",
} as const;

type AbilityKey = keyof typeof labels;

export function AbilityBars({ abilities }: { abilities: Record<AbilityKey, number> }) {
  return (
    <section aria-label="能力画像">
      {Object.entries(labels).map(([key, label]) => (
        <div key={key}>
          <span>{label}</span>
          <progress value={abilities[key as AbilityKey]} max={100} />
        </div>
      ))}
    </section>
  );
}
