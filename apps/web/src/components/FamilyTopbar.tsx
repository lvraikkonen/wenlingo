"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { demoLogin, getMyAlphaChildren } from "../lib/api";
import type { Student } from "../lib/types";

function shouldLoadDemoStudents(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("status" in error)) {
    return false;
  }

  const status = (error as { status?: unknown }).status;
  return status === 401 || status === 404;
}

export function FamilyTopbar({
  currentStudentId,
}: {
  currentStudentId: string;
}) {
  const [students, setStudents] = useState<Student[]>([]);
  const [alphaStudentName, setAlphaStudentName] = useState<{
    studentId: string;
    name: string;
  } | null>(null);

  useEffect(() => {
    let mounted = true;
    setAlphaStudentName(null);
    setStudents([]);

    const loadDemoStudents = () => {
      demoLogin()
        .then((result) => {
          if (mounted) {
            setStudents(result.students);
          }
        })
        .catch(() => {
          if (mounted) {
            setStudents([]);
          }
        });
    };

    try {
      getMyAlphaChildren()
        .then((result) => {
          if (!mounted) {
            return;
          }
          if (result.children.length === 0) {
            loadDemoStudents();
            return;
          }

          const currentChild = result.children.find(
            (child) => child.id === currentStudentId,
          );
          setAlphaStudentName({
            studentId: currentStudentId,
            name: currentChild?.name ?? currentStudentId,
          });
        })
        .catch((error: unknown) => {
          if (shouldLoadDemoStudents(error)) {
            loadDemoStudents();
          }
        });
    } catch {
      setStudents([]);
    }

    return () => {
      mounted = false;
    };
  }, [currentStudentId]);

  const sortedStudents = useMemo(
    () => [...students].sort((left, right) => left.id.localeCompare(right.id)),
    [students],
  );
  const currentStudent = sortedStudents.find(
    (student) => student.id === currentStudentId,
  );
  const currentStudentName = currentStudent?.name ?? currentStudentId;

  if (alphaStudentName) {
    const currentAlphaStudentName =
      alphaStudentName.studentId === currentStudentId
        ? alphaStudentName.name
        : currentStudentId;

    return (
      <header className="border-b border-[var(--wen-border)] bg-white px-5 py-4 sm:px-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={`/children/${currentStudentId}`}
              className="text-lg font-bold text-[var(--wen-orange)]"
            >
              小文星球
            </Link>
            <span className="rounded-lg bg-[var(--wen-bg)] px-3 py-1 text-sm font-semibold">
              当前孩子：{currentAlphaStudentName}
            </span>
          </div>

          <nav
            aria-label="Alpha 导航"
            className="flex flex-wrap items-center gap-2 text-sm font-semibold"
          >
            <Link className="rounded-lg px-3 py-2" href={`/children/${currentStudentId}`}>
              Dashboard
            </Link>
            <Link
              className="rounded-lg px-3 py-2"
              href={`/children/${currentStudentId}/essay`}
            >
              作文城堡
            </Link>
            <Link
              className="rounded-lg px-3 py-2"
              href={`/children/${currentStudentId}/sentence`}
            >
              句子工坊
            </Link>
            <Link
              className="rounded-lg border border-[var(--wen-border)] px-3 py-2"
              href="/parent/children"
            >
              返回孩子列表
            </Link>
          </nav>
        </div>
      </header>
    );
  }

  return (
    <header className="border-b border-[var(--wen-border)] bg-white px-5 py-4 sm:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <Link
            href={`/children/${currentStudentId}`}
            className="text-lg font-bold text-[var(--wen-orange)]"
          >
            小文星球
          </Link>
          <span className="rounded-lg bg-[var(--wen-bg)] px-3 py-1 text-sm font-semibold">
            当前孩子：{currentStudentName}
          </span>
        </div>

        <nav
          aria-label="主导航"
          className="flex flex-wrap items-center gap-2 text-sm font-semibold"
        >
          <Link className="rounded-lg px-3 py-2" href={`/children/${currentStudentId}`}>
            Dashboard
          </Link>
          <Link
            className="rounded-lg px-3 py-2"
            href={`/children/${currentStudentId}/essay`}
          >
            作文城堡
          </Link>
          <Link
            className="rounded-lg px-3 py-2"
            href={`/children/${currentStudentId}/sentence`}
          >
            句子工坊
          </Link>
          <Link
            className="rounded-lg px-3 py-2"
            href={`/parent/${currentStudentId}/report`}
          >
            家长报告
          </Link>
        </nav>

        <nav
          aria-label="孩子切换"
          className="flex flex-wrap items-center gap-2 text-sm"
        >
          {sortedStudents.map((student) => (
            <Link
              key={student.id}
              href={`/children/${student.id}`}
              className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold"
            >
              {student.name}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
