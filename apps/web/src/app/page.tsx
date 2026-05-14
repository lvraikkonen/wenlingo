"use client";

import Link from "next/link";
import { useState } from "react";
import { demoLogin } from "../lib/api";
import type { Student } from "../lib/types";

export default function Home() {
  const [students, setStudents] = useState<Student[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleDemoLogin() {
    setIsLoading(true);
    setError("");

    try {
      const result = await demoLogin();
      setStudents(
        [...result.students].sort((first, second) =>
          first.id.localeCompare(second.id),
        ),
      );
    } catch {
      setError("进入失败，请稍后再试。");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <h1 className="text-4xl font-bold text-[var(--wen-ink)]">小文星球</h1>
      <button
        type="button"
        onClick={handleDemoLogin}
        disabled={isLoading}
        className="mt-6 rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white shadow-sm transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
      >
        进入家庭内测
      </button>
      {isLoading ? (
        <p role="status" className="mt-4 text-sm text-[var(--wen-muted)]">
          正在进入...
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 text-sm font-medium text-red-600">
          {error}
        </p>
      ) : null}
      {students.length > 0 ? (
        <section aria-label="孩子选择" className="mt-8 flex flex-wrap gap-3">
          {students.map((student) => (
            <Link
              key={student.id}
              href={`/children/${student.id}`}
              className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-surface)] px-4 py-3 font-semibold text-[var(--wen-ink)] shadow-sm transition hover:border-[var(--wen-sky)] hover:text-[var(--wen-sky)]"
            >
              {student.name}
            </Link>
          ))}
        </section>
      ) : null}
    </main>
  );
}
