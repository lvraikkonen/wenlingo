"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { createReadingSession } from "../../../../lib/api";

export default function ReadingPage({
  params,
}: {
  params: { studentId: string };
}) {
  const { studentId } = params;
  const [mainIdea, setMainIdea] = useState(
    "春天来了，小河和鸟儿都很热闹。",
  );
  const [detail, setDetail] = useState("小河发出哗啦啦的声音。");
  const [transfer, setTransfer] = useState("写景可以写声音。");
  const [transferTip, setTransferTip] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const result = await createReadingSession(studentId, {
        main_idea: mainIdea,
        detail,
        transfer,
      });

      setTransferTip(result.transfer_tip);
    } catch {
      setError("提交失败，请稍后再试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>春天的声音</h1>
      <article>
        <h2>春天的声音</h2>
        <p>小河哗啦啦地唱着歌，柳树在风里轻轻摇。</p>
        <p>小鸟站在枝头叫着，好像在告诉大家：春天来了。</p>
      </article>
      <form onSubmit={handleSubmit}>
        <label>
          主要内容
          <textarea
            value={mainIdea}
            onChange={(event) => setMainIdea(event.target.value)}
          />
        </label>
        <label>
          文中细节
          <textarea
            value={detail}
            onChange={(event) => setDetail(event.target.value)}
          />
        </label>
        <label>
          迁移练习
          <textarea
            value={transfer}
            onChange={(event) => setTransfer(event.target.value)}
          />
        </label>
        <button type="submit" disabled={isSubmitting}>
          提交阅读答案
        </button>
      </form>
      {transferTip ? <p>{transferTip}</p> : null}
      {isSubmitting ? <p role="status">正在提交...</p> : null}
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
