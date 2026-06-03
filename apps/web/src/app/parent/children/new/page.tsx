"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { createMyAlphaChild, isUnauthorizedError } from "../../../../lib/api";

export default function NewChildPage() {
  const router = useRouter();
  const [nickname, setNickname] = useState("");
  const [grade, setGrade] = useState("4");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [createdChild, setCreatedChild] = useState<{
    name: string;
    dashboardUrl: string;
  } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    const trimmedNickname = nickname.trim();
    if (!trimmedNickname) {
      setError("请填写孩子昵称。");
      return;
    }
    if (trimmedNickname.length > 24) {
      setError("孩子昵称最多 24 个字。");
      return;
    }
    const gradeNumber = Number(grade);
    if (!Number.isInteger(gradeNumber) || gradeNumber < 3 || gradeNumber > 6) {
      setError("请选择 3-6 年级。");
      return;
    }
    setIsSubmitting(true);
    setError("");
    try {
      const response = await createMyAlphaChild({
        nickname: trimmedNickname,
        grade: gradeNumber,
      });
      setCreatedChild({
        name: response.child.name,
        dashboardUrl: response.dashboard_url,
      });
    } catch (requestError: unknown) {
      if (isUnauthorizedError(requestError)) {
        router.replace("/alpha/start");
      } else {
        setError("创建孩子档案失败，请稍后再试。");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (createdChild) {
    return (
      <main className="min-h-screen px-5 py-8 sm:px-8">
        <section className="mx-auto max-w-2xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-[var(--wen-muted)]">
            Child Handoff
          </p>
          <h1 className="mt-3 text-3xl font-bold">
            {createdChild.name}已加入小文星球！
          </h1>
          <p className="mt-4 text-[var(--wen-muted)]">
            现在可以把设备交给{createdChild.name}，开始第一次语文冒险。
          </p>
          <Link
            href={createdChild.dashboardUrl}
            className="mt-6 inline-flex rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white"
          >
            进入小文星球
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-2xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
        <p className="text-sm font-semibold text-[var(--wen-muted)]">
          New Child
        </p>
        <h1 className="mt-3 text-3xl font-bold">创建孩子档案</h1>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <label className="block font-semibold">
            孩子怎么称呼？
            <input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              maxLength={24}
              className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
            />
          </label>
          <label className="block font-semibold">
            孩子现在几年级？
            <select
              value={grade}
              onChange={(event) => setGrade(event.target.value)}
              className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
            >
              <option value="3">三年级</option>
              <option value="4">四年级</option>
              <option value="5">五年级</option>
              <option value="6">六年级</option>
            </select>
          </label>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            创建孩子档案
          </button>
        </form>
        {error ? (
          <p role="alert" className="mt-4 text-sm font-semibold text-red-600">
            {error}
          </p>
        ) : null}
      </section>
    </main>
  );
}
