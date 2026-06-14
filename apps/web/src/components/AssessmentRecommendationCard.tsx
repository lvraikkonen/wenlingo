import Link from "next/link";
import { Sparkles } from "lucide-react";

export function AssessmentRecommendationCard({
  studentId,
  continueLabel,
  onContinue,
}: {
  studentId: string;
  continueLabel: string;
  onContinue: () => void;
}) {
  return (
    <section
      aria-label="入门小试炼推荐"
      className="rounded-lg border border-[var(--wen-orange)] bg-[var(--wen-orange-soft)] p-4"
    >
      <div className="flex items-start gap-3">
        <Sparkles
          aria-hidden="true"
          className="mt-1 h-5 w-5 shrink-0 text-[var(--wen-orange)]"
        />
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold">先点亮第一张能力草图</h2>
          <p className="mt-2 text-sm text-[var(--wen-muted)]">
            做一个 3-5 分钟的小试点，AI 教练就能更懂你。
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link
              className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 text-sm font-bold text-white"
              href={`/children/${studentId}/assessment`}
            >
              先去小试炼
            </Link>
            <button
              className="rounded-lg border border-[var(--wen-border)] bg-white px-4 py-2 text-sm font-bold"
              type="button"
              onClick={onContinue}
            >
              {continueLabel}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
