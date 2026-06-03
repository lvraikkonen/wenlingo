"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  getMyAlphaChildren,
  isUnauthorizedError,
  recordAlphaEvent,
} from "../../../lib/api";
import { getStoredAlphaSessionId } from "../../../lib/alphaSession";
import type { AlphaChildrenResponse } from "../../../lib/types";

export default function ParentChildrenPage() {
  const router = useRouter();
  const [data, setData] = useState<AlphaChildrenResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;
    getMyAlphaChildren()
      .then((response) => {
        if (isMounted) {
          setData(response);
          recordAlphaEvent({
            event_type: "parent_children_viewed",
            parent_id: response.parent.id,
            alpha_session_id: getStoredAlphaSessionId(),
            payload: { path: "/parent/children", status: "viewed" },
          });
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          if (isUnauthorizedError(error)) {
            router.replace("/alpha/start");
          } else {
            setError("孩子列表加载失败，请稍后再试。");
          }
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [router]);

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-4xl">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-[var(--wen-muted)]">
              Alpha Family
            </p>
            <h1 className="mt-2 text-3xl font-bold">我的孩子</h1>
            {data?.parent.display_name ? (
              <p className="mt-2 text-[var(--wen-muted)]">
                {data.parent.display_name}，可以从这里进入孩子空间或查看成长摘要。
              </p>
            ) : null}
          </div>
          <Link
            href="/parent/children/new"
            className="inline-flex w-fit rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white"
          >
            创建孩子档案
          </Link>
        </div>

        {isLoading ? (
          <p className="mt-8 rounded-lg border border-[var(--wen-border)] bg-white p-5 text-[var(--wen-muted)]">
            正在加载孩子档案...
          </p>
        ) : null}

        {error ? (
          <p
            role="alert"
            className="mt-8 rounded-lg border border-red-200 bg-red-50 p-5 font-semibold text-red-700"
          >
            {error}
          </p>
        ) : null}

        {!isLoading && !error && data?.children.length === 0 ? (
          <div className="mt-8 rounded-lg border border-[var(--wen-border)] bg-white p-6">
            <p className="font-semibold">还没有孩子档案。</p>
            <p className="mt-2 text-[var(--wen-muted)]">
              创建第一个孩子档案后，就可以把设备交给孩子开始语文冒险。
            </p>
          </div>
        ) : null}

        {!isLoading && !error && data?.children.length ? (
          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            {data.children.map((child) => (
              <article
                key={child.id}
                className="rounded-lg border border-[var(--wen-border)] bg-white p-5 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-bold">
                      {child.name || child.nickname}
                    </h2>
                    <p className="mt-1 text-sm font-semibold text-[var(--wen-muted)]">
                      {child.grade_label}
                    </p>
                  </div>
                  <span className="rounded-lg bg-[var(--wen-bg)] px-3 py-2 text-sm font-semibold">
                    {child.assessment_completed
                      ? "已完成入门小试炼"
                      : "等待入门小试炼"}
                  </span>
                </div>
                <div className="mt-5 flex flex-wrap gap-3">
                  <Link
                    href={child.dashboard_url}
                    onClick={() => {
                      recordAlphaEvent({
                        event_type: "child_handoff_clicked",
                        parent_id: data.parent.id,
                        student_id: child.id,
                        alpha_session_id: getStoredAlphaSessionId(),
                        payload: { path: "/parent/children", status: "clicked" },
                      });
                    }}
                    className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
                  >
                    进入孩子空间
                  </Link>
                  <Link
                    href={child.summary_url}
                    className="rounded-lg border border-[var(--wen-border)] bg-white px-4 py-2 font-semibold"
                  >
                    查看成长摘要
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}
