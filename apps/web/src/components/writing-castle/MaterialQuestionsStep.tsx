"use client";

import type { MaterialAnswer, WritingCastleEssay } from "../../lib/types";

type MaterialQuestion = WritingCastleEssay["material_card"]["questions"][number];

export function MaterialQuestionsStep({
  questions,
  answers,
  onAnswersChange,
  onContinue,
  onDirectWrite,
}: {
  questions: MaterialQuestion[];
  answers: MaterialAnswer[];
  onAnswersChange: (answers: MaterialAnswer[]) => void;
  onContinue: () => void;
  onDirectWrite: () => void;
}) {
  function updateAnswer(questionId: string, text: string) {
    onAnswersChange(
      answers.map((answer) =>
        answer.question_id === questionId
          ? { ...answer, text, skipped: text.trim().length === 0 }
          : answer,
      ),
    );
  }

  return (
    <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <p className="text-sm font-bold text-[var(--wen-muted)]">
        第 2 步 / 共 4 步：想一想素材
      </p>
      <div className="mt-5 space-y-4">
        {questions.map((question) => {
          const answer =
            answers.find((item) => item.question_id === question.id)?.text ??
            "";

          return (
            <label key={question.id} className="block font-semibold">
              {question.text}
              <textarea
                className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                value={answer}
                onChange={(event) =>
                  updateAnswer(question.id, event.target.value)
                }
                placeholder={question.hint}
              />
            </label>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
          type="button"
          onClick={onContinue}
        >
          整理素材卡
        </button>
        <button
          className="rounded-lg border border-[var(--wen-border)] px-4 py-2 font-semibold"
          type="button"
          onClick={onDirectWrite}
        >
          我想直接开始写
        </button>
      </div>
    </section>
  );
}
