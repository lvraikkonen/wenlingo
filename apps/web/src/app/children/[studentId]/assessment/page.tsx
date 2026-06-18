"use client";

import Link from "next/link";
import { ArrowRight, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { use, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { FeedbackReaction } from "../../../../components/FeedbackReaction";
import { createAssessment } from "../../../../lib/api";
import type { AbilitySketch, AssessmentResponse } from "../../../../lib/api";

const FIXED_SOURCE_SENTENCE = "公园很美。";
const WRITING_PROMPT = "写一写你最近一次开心的经历";

type Step = "intro" | "sentence" | "writing" | "sketch";

const abilityLabels = {
  reading_power: "读懂力",
  specific_writing_power: "写具体力",
  revision_power: "会修改力",
} as const;

type AbilityKey = keyof typeof abilityLabels;

function radarPoint(index: number, value: number) {
  const angle = -Math.PI / 2 + index * ((Math.PI * 2) / 3);
  const radius = (Math.max(0, Math.min(100, value)) / 100) * 58;
  const center = 80;
  return {
    x: center + Math.cos(angle) * radius,
    y: center + Math.sin(angle) * radius,
  };
}

function polygonPoints(sketch: AbilitySketch) {
  return (Object.keys(abilityLabels) as AbilityKey[])
    .map((key, index) => {
      const point = radarPoint(index, sketch[key]);
      return `${point.x},${point.y}`;
    })
    .join(" ");
}

function strongestSignal(sketch: AbilitySketch) {
  const entries = (Object.keys(abilityLabels) as AbilityKey[]).map((key) => ({
    key,
    value: sketch[key],
  }));
  const strongest = entries.reduce((best, item) =>
    item.value > best.value ? item : best,
  );

  if (strongest.key === "specific_writing_power") {
    return "写具体力已经露出第一个亮点。";
  }
  if (strongest.key === "reading_power") {
    return "读懂力保持稳定，后面可以用阅读试炼点亮更多证据。";
  }
  return "会修改力保持稳定，二稿任务会继续点亮它。";
}

function AbilityRadar({ sketch }: { sketch: AbilitySketch }) {
  const keys = Object.keys(abilityLabels) as AbilityKey[];
  const guide = "80,22 130.229,109 29.771,109";

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr] lg:items-center">
      <svg
        viewBox="0 0 160 150"
        role="img"
        aria-label="第一张能力草图雷达图"
        className="h-56 w-full max-w-64 justify-self-center"
      >
        <polygon
          points={guide}
          fill="none"
          stroke="var(--wen-border)"
          strokeWidth="2"
        />
        <polygon
          points="80,41.333 113.486,99 46.514,99"
          fill="none"
          stroke="var(--wen-border)"
          strokeWidth="1"
        />
        <polygon
          points={polygonPoints(sketch)}
          fill="rgba(74, 168, 255, 0.24)"
          stroke="var(--wen-sky)"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        {keys.map((key, index) => {
          const point = radarPoint(index, sketch[key]);
          return (
            <circle
              key={key}
              cx={point.x}
              cy={point.y}
              r="4"
              fill="var(--wen-orange)"
            />
          );
        })}
        <text
          x="80"
          y="14"
          textAnchor="middle"
          className="fill-[var(--wen-ink)] text-[9px]"
        >
          读懂力
        </text>
        <text
          x="138"
          y="124"
          textAnchor="middle"
          className="fill-[var(--wen-ink)] text-[9px]"
        >
          <tspan>写</tspan>
          <tspan>具体力</tspan>
        </text>
        <text
          x="15"
          y="124"
          textAnchor="middle"
          className="fill-[var(--wen-ink)] text-[9px]"
        >
          会修改力
        </text>
      </svg>
      <div className="space-y-3">
        <p className="rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
          {strongestSignal(sketch)}
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          {keys.map((key) => {
            const waiting =
              key === "reading_power" && sketch[key] === 40
                ? "等待阅读试炼"
                : key === "revision_power" && sketch[key] === 40
                  ? "等待二稿试炼"
                  : `${sketch[key]} / 100`;

            return (
              <div
                key={key}
                className="rounded-lg border border-[var(--wen-border)] bg-white p-3"
              >
                <p className="font-semibold">{abilityLabels[key]}</p>
                <p className="mt-1 text-sm text-[var(--wen-muted)]">
                  {waiting}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function AssessmentPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);

  return <AssessmentPageContent key={studentId} studentId={studentId} />;
}

function AssessmentPageContent({ studentId }: { studentId: string }) {
  const activeStudentId = useRef<string | null>(studentId);
  const [step, setStep] = useState<Step>("intro");
  const [sentenceAfter, setSentenceAfter] = useState("");
  const [shortWriting, setShortWriting] = useState("");
  const [result, setResult] = useState<AssessmentResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const canContinueSentence = sentenceAfter.trim().length > 0;
  const canSubmitWriting = shortWriting.trim().length >= 20;

  useEffect(() => {
    activeStudentId.current = studentId;

    return () => {
      activeStudentId.current = null;
    };
  }, [studentId]);

  const progress = useMemo(
    () =>
      [
        { key: "intro", label: "开始" },
        { key: "sentence", label: "句子魔法" },
        { key: "writing", label: "小写作" },
        { key: "sketch", label: "能力草图" },
      ] as const,
    [],
  );

  async function submitAssessment() {
    if (!canSubmitWriting || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError("");
    const requestStudentId = studentId;

    try {
      const response = await createAssessment(studentId, {
        sentence_before: FIXED_SOURCE_SENTENCE,
        sentence_after: sentenceAfter,
        short_writing: shortWriting,
      });

      if (activeStudentId.current !== requestStudentId) {
        return;
      }
      setResult(response);
      setStep("sketch");
    } catch {
      if (activeStudentId.current !== requestStudentId) {
        return;
      }
      setError("这次小试炼没有提交成功。不是你的问题，检查一下网络后再试一次。");
    } finally {
      if (activeStudentId.current === requestStudentId) {
        setIsSubmitting(false);
      }
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitAssessment();
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <nav
          aria-label="小试炼进度"
          className="flex flex-wrap gap-2 text-sm font-semibold"
        >
          {progress.map((item) => (
            <span
              key={item.key}
              aria-current={step === item.key ? "step" : undefined}
              className={`rounded-lg px-3 py-2 ${
                step === item.key
                  ? "bg-[var(--wen-orange)] text-white"
                  : "bg-white text-[var(--wen-muted)]"
              }`}
            >
              {item.label}
            </span>
          ))}
        </nav>

        {step === "intro" ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <p className="text-sm font-semibold text-[var(--wen-muted)]">
              约 3-5 分钟
            </p>
            <h1 className="mt-3 text-3xl font-bold">认识你的写作超能力</h1>
            <p className="mt-4 text-[var(--wen-muted)]">
              先完成一句话升级，再写一小段开心经历。
            </p>
            <button
              type="button"
              onClick={() => setStep("sentence")}
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white shadow-sm"
            >
              <Sparkles size={18} aria-hidden="true" />
              开始小试炼
            </button>
          </section>
        ) : null}

        {step === "sentence" ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <h1 className="text-2xl font-bold">句子魔法</h1>
            <div className="mt-5 rounded-lg bg-[var(--wen-bg)] p-4">
              <p className="text-sm font-semibold text-[var(--wen-muted)]">
                原句
              </p>
              <p className="mt-2 text-xl font-bold">{FIXED_SOURCE_SENTENCE}</p>
            </div>
            <label className="mt-5 block font-semibold">
              升级后的句子
              <textarea
                value={sentenceAfter}
                onChange={(event) => setSentenceAfter(event.target.value)}
                maxLength={500}
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
              />
            </label>
            <button
              type="button"
              onClick={() => setStep("writing")}
              disabled={!canContinueSentence}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              继续写小作文
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          </section>
        ) : null}

        {step === "writing" ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <h1 className="text-2xl font-bold">小写作</h1>
            <p className="mt-3 rounded-lg bg-[var(--wen-bg)] px-4 py-3 font-semibold">
              {WRITING_PROMPT}
            </p>
            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <label className="block font-semibold">
                小写作
                <textarea
                  value={shortWriting}
                  onChange={(event) => setShortWriting(event.target.value)}
                  minLength={20}
                  maxLength={500}
                  className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                />
              </label>
              <button
                type="submit"
                disabled={!canSubmitWriting || isSubmitting}
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles size={18} aria-hidden="true" />
                )}
                生成能力草图
              </button>
            </form>
            {isSubmitting ? (
              <p
                role="status"
                className="mt-4 rounded-lg bg-[var(--wen-bg)] px-4 py-3 text-sm font-semibold text-[var(--wen-orange)]"
              >
                AI 教练正在整理第一张能力草图
              </p>
            ) : null}
            {error ? (
              <div
                role="alert"
                className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700"
              >
                <p>{error}</p>
                <button
                  type="button"
                  onClick={submitAssessment}
                  disabled={isSubmitting}
                  className="mt-3 inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-[var(--wen-ink)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <RotateCcw size={16} aria-hidden="true" />
                  再试一次
                </button>
              </div>
            ) : null}
          </section>
        ) : null}

        {step === "sketch" && result ? (
          <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
            <p className="text-sm font-semibold text-[var(--wen-muted)]">
              {result.assessment.summary}
            </p>
            <h1 className="mt-3 text-2xl font-bold">第一张能力草图</h1>
            <div className="mt-6">
              <AbilityRadar sketch={result.ability_sketch} />
            </div>
            <div className="mt-6">
              <FeedbackReaction
                key={`${studentId}:assessment:${result.assessment.id}`}
                studentId={studentId}
                targetType="assessment"
                targetId={result.assessment.id}
                initialReaction={result.assessment.reaction ?? null}
              />
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <span className="rounded-lg bg-[var(--wen-bg)] px-3 py-2 text-sm font-semibold">
                +{result.settlement.xp_delta} XP
              </span>
              <Link
                href={`/children/${studentId}`}
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white"
              >
                回到 Dashboard
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </div>
          </section>
        ) : null}
      </div>
    </main>
  );
}
