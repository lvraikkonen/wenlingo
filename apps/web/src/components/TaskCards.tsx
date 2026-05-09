import type { RecommendedTask } from "../lib/types";

export function TaskCards({
  main,
  quick,
}: {
  main: RecommendedTask;
  quick: RecommendedTask;
}) {
  return (
    <section aria-label="今日推荐">
      <h2>今日推荐</h2>
      {[
        { label: "主线", task: main },
        { label: "快练", task: quick },
      ].map(({ label, task }) => (
        <article key={`${label}-${task.kind}-${task.title}`}>
          <h3>
            {label}：{task.title}
          </h3>
          <p>{task.focus}</p>
          <span>{task.minutes} 分钟</span>
        </article>
      ))}
    </section>
  );
}
