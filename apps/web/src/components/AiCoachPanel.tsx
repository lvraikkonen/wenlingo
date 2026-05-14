export function AiCoachPanel({ message }: { message: string }) {
  return (
    <aside
      aria-label="AI 教练"
      className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm"
    >
      <strong className="text-xl">AI 教练</strong>
      <p className="mt-3 text-[var(--wen-muted)]">{message}</p>
    </aside>
  );
}
