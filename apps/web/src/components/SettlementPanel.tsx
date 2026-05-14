import type { Settlement } from "../lib/api";

export function SettlementPanel({
  settlement,
}: {
  settlement: Settlement;
}) {
  return (
    <section
      aria-label="战斗结算"
      className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
    >
      <h2 className="text-xl font-bold">战斗结算</h2>
      <div className="mt-4 flex flex-wrap gap-3">
        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-2 font-semibold">
          +{settlement.xp_delta} XP
        </p>
        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-2 font-semibold">
          等级 {settlement.level_after}
        </p>
        {settlement.badge_code ? (
          <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-2 font-semibold">
            {settlement.badge_code}
          </p>
        ) : null}
      </div>
    </section>
  );
}
