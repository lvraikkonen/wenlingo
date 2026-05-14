import Link from "next/link";
import { PenLine, Timer } from "lucide-react";
import type { RecommendedTask } from "../lib/types";

export function TaskCards({
  studentId,
  main,
  quick,
}: {
  studentId: string;
  main: RecommendedTask;
  quick: RecommendedTask;
}) {
  return (
    <section
      aria-label="今日推荐"
      className="space-y-4"
    >
      <h2 className="text-xl font-bold">今日推荐</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { label: "主线", task: main },
          { label: "快练", task: quick },
        ].map(({ label, task }) => {
          const href =
            task.kind === "essay"
              ? `/children/${studentId}/essay`
              : `/children/${studentId}/${task.kind}`;

          return (
            <article
              key={`${label}-${task.kind}-${task.title}`}
              className="rounded-lg border border-[var(--wen-border)] p-4"
            >
              <p className="text-sm font-semibold text-[var(--wen-muted)]">
                {label}
              </p>
              <h3 className="mt-1 text-lg font-bold">
                {label}：{task.title}
              </h3>
              <p className="mt-2 text-[var(--wen-muted)]">{task.focus}</p>
              <span className="mt-3 inline-flex items-center gap-2 text-sm font-semibold">
                <Timer size={16} aria-hidden="true" />
                {task.minutes} 分钟
              </span>
              <div className="mt-4">
                <Link
                  href={href}
                  className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
                >
                  <PenLine size={18} aria-hidden="true" />
                  {task.kind === "essay" ? "去写作文" : "开始任务"}
                </Link>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
