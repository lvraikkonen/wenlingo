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
    <main>
      <h1>小文星球</h1>
      <button type="button" onClick={handleDemoLogin} disabled={isLoading}>
        进入家庭内测
      </button>
      {isLoading ? <p role="status">正在进入...</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {students.length > 0 ? (
        <section aria-label="孩子选择">
          {students.map((student) => (
            <Link key={student.id} href={`/children/${student.id}`}>
              {student.name}
            </Link>
          ))}
        </section>
      ) : null}
    </main>
  );
}
