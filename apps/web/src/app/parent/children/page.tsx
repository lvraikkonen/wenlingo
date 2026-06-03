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
import { bindPhone } from "../../../lib/authSession";
import type { AlphaChildrenResponse } from "../../../lib/types";

export default function ParentChildrenPage() {
  const router = useRouter();
  const [data, setData] = useState<AlphaChildrenResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [phone, setPhone] = useState("");
  const [phoneMasked, setPhoneMasked] = useState("");
  const [phoneError, setPhoneError] = useState("");
  const [isSavingPhone, setIsSavingPhone] = useState(false);

  const boundPhoneMasked = phoneMasked || data?.account?.phone_masked || "";

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

  async function handlePhoneSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedPhone = phone.trim();
    setPhoneError("");
    setIsSavingPhone(true);

    try {
      const response = await bindPhone({ phone: trimmedPhone });
      setPhoneMasked(response.phone_masked);
      setData((current) =>
        current
          ? {
              ...current,
              account: {
                email_masked: current.account?.email_masked ?? "",
                phone_bound: response.phone_bound,
                phone_masked: response.phone_masked,
              },
            }
          : current,
      );
      setPhone("");
    } catch {
      setPhoneError("手机号保存失败，请稍后再试。");
    } finally {
      setIsSavingPhone(false);
    }
  }

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
            {data ? (
              <form className="mt-4 max-w-md" onSubmit={handlePhoneSubmit}>
                <label
                  className="text-sm font-semibold text-[var(--wen-muted)]"
                  htmlFor="parent-phone"
                >
                  手机号（可选）
                </label>
                <p className="mt-1 text-sm text-[var(--wen-muted)]">
                  可选填写，V0.5a 不用于短信登录。
                </p>
                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                  <input
                    id="parent-phone"
                    className="min-w-0 flex-1 rounded-lg border border-[var(--wen-border)] bg-white px-3 py-2"
                    inputMode="tel"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                  />
                  <button
                    className="rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white disabled:opacity-60"
                    disabled={isSavingPhone}
                    type="submit"
                  >
                    {isSavingPhone ? "保存中..." : "保存手机号"}
                  </button>
                </div>
                {boundPhoneMasked ? (
                  <p className="mt-2 text-sm font-semibold text-emerald-700">
                    已绑定 {boundPhoneMasked}
                  </p>
                ) : null}
                {phoneError ? (
                  <p className="mt-2 text-sm font-semibold text-red-700" role="alert">
                    {phoneError}
                  </p>
                ) : null}
              </form>
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
