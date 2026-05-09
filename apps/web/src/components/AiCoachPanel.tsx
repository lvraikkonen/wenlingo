export function AiCoachPanel({ message }: { message: string }) {
  return (
    <aside aria-label="AI 教练">
      <strong>AI 教练</strong>
      <p>{message}</p>
    </aside>
  );
}
