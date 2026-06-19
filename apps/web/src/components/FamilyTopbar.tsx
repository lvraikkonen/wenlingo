"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getMyAlphaChildren } from "../lib/api";

type FamilyTopbarState = {
  currentStudentId: string;
  studentName: string;
  hasAlphaChildren: boolean;
};

export function FamilyTopbar({
  currentStudentId,
}: {
  currentStudentId: string;
}) {
  const [topbarState, setTopbarState] = useState<FamilyTopbarState>(() => ({
    currentStudentId,
    studentName: currentStudentId,
    hasAlphaChildren: false,
  }));
  const isCurrentTopbarState = topbarState.currentStudentId === currentStudentId;
  const currentStudentName = isCurrentTopbarState
    ? topbarState.studentName
    : currentStudentId;

  useEffect(() => {
    let mounted = true;

    try {
      getMyAlphaChildren()
        .then((result) => {
          if (!mounted) {
            return;
          }

          const currentChild = result.children.find(
            (child) => child.id === currentStudentId,
          );
          setTopbarState({
            currentStudentId,
            studentName: currentChild?.name ?? currentStudentId,
            hasAlphaChildren: result.children.length > 0,
          });
        })
        .catch(() => {
          if (mounted) {
            setTopbarState({
              currentStudentId,
              studentName: currentStudentId,
              hasAlphaChildren: false,
            });
          }
        });
    } catch {
      setTopbarState({
        currentStudentId,
        studentName: currentStudentId,
        hasAlphaChildren: false,
      });
    }

    return () => {
      mounted = false;
    };
  }, [currentStudentId]);

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
          aria-label="Alpha 导航"
          className="flex flex-wrap items-center gap-2 text-sm font-semibold"
        >
          <Link
            className="rounded-lg px-3 py-2"
            href={`/children/${currentStudentId}`}
          >
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
            href={`/parent/children/${currentStudentId}/summary`}
          >
            家长摘要
          </Link>
          <Link
            className="rounded-lg px-3 py-2"
            href={`/parent/${currentStudentId}/report`}
          >
            家长报告
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
