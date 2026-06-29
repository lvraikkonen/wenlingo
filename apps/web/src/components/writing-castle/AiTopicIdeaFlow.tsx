"use client";

import { useState } from "react";
import { createAiTopicEssay, generateAiTopicIdeas } from "../../lib/api";
import type {
  AiTopicIdea,
  AiTopicIdeasResponse,
  WritingCastleEssay,
} from "../../lib/types";

export function AiTopicIdeaFlow({
  studentId,
  onEssayCreated,
}: {
  studentId: string;
  onEssayCreated: (essay: WritingCastleEssay) => void;
}) {
  const [interestText, setInterestText] = useState("");
  const [ideasResponse, setIdeasResponse] = useState<AiTopicIdeasResponse | null>(
    null,
  );
  const [error, setError] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedIdeaId, setSelectedIdeaId] = useState<string | null>(null);

  async function generateIdeas() {
    setIsGenerating(true);
    setError("");
    setIdeasResponse(null);
    try {
      const response = await generateAiTopicIdeas(studentId, {
        interest_text: interestText.trim(),
      });
      setIdeasResponse(response);
    } catch {
      setError("题目灵感暂时没有生成成功。可以稍后再试，也可以先选择课内同步作文或直接写初稿。");
    } finally {
      setIsGenerating(false);
    }
  }

  async function selectIdea(idea: AiTopicIdea) {
    if (!ideasResponse || selectedIdeaId) {
      return;
    }
    setSelectedIdeaId(idea.id);
    setError("");
    try {
      const response = await createAiTopicEssay(studentId, {
        idea_batch_id: ideasResponse.idea_batch_id,
        selected_idea_id: idea.id,
      });
      onEssayCreated(response.essay);
    } catch {
      setSelectedIdeaId(null);
      setError("这个题目暂时没有进入写作步骤。可以重新选择一次。");
    }
  }

  return (
    <section className="rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
      <label className="block font-semibold">
        兴趣或想写的方向
        <textarea
          className="mt-2 w-full rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
          value={interestText}
          onChange={(event) => setInterestText(event.target.value)}
        />
      </label>
      <button
        className="mt-4 rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white disabled:opacity-60"
        type="button"
        disabled={isGenerating || Boolean(selectedIdeaId)}
        onClick={generateIdeas}
      >
        生成题目灵感
      </button>
      {isGenerating ? (
        <p role="status" className="mt-3 font-semibold">
          正在生成题目灵感……
        </p>
      ) : null}
      {error ? (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-[var(--wen-orange)] bg-white p-4 font-semibold"
        >
          {error}
        </p>
      ) : null}
      {ideasResponse ? (
        <div className="mt-5 grid gap-3">
          {ideasResponse.ideas.map((idea) => (
            <article
              key={idea.id}
              className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-4"
            >
              <h2 className="text-lg font-bold">{idea.title}</h2>
              <p className="mt-2 text-sm font-semibold text-[var(--wen-muted)]">
                {idea.why_it_fits_child_interest}
              </p>
              <p className="mt-2 text-sm">{idea.practice_focus}</p>
              <p className="mt-2 text-sm">{idea.child_safe_prompt}</p>
              <button
                className="mt-4 rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white disabled:opacity-60"
                type="button"
                disabled={Boolean(selectedIdeaId)}
                onClick={() => selectIdea(idea)}
              >
                选择这个题目
              </button>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
