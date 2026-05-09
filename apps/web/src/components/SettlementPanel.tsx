export function SettlementPanel({
  settlement,
}: {
  settlement: {
    xp_delta: number;
    level_after: number;
    badge_code?: string;
  };
}) {
  return (
    <section aria-label="战斗结算">
      <h2>战斗结算</h2>
      <p>+{settlement.xp_delta} XP</p>
      <p>等级 {settlement.level_after}</p>
      {settlement.badge_code ? <p>{settlement.badge_code}</p> : null}
    </section>
  );
}
