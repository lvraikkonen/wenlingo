"use client";

import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import type { FormEvent } from "react";
import { createAlphaParent } from "../../../lib/api";
import {
  clearStoredAlphaParentId,
  getStoredAlphaParentId,
  setStoredAlphaParentId,
} from "../../../lib/alphaParent";

const ALPHA_PARENT_STORAGE_EVENT = "wenlingo-alpha-parent-storage";

function subscribeToAlphaParentStorage(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(ALPHA_PARENT_STORAGE_EVENT, onStoreChange);

  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(ALPHA_PARENT_STORAGE_EVENT, onStoreChange);
  };
}

export default function AlphaStartPage() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("Alpha 家长");
  const storedParentId = useSyncExternalStore(
    subscribeToAlphaParentStorage,
    getStoredAlphaParentId,
    () => null,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }
    setIsSubmitting(true);
    setError("");
    try {
      const response = await createAlphaParent({ display_name: displayName });
      setStoredAlphaParentId(response.parent.id);
      router.push(response.children_url);
    } catch {
      setError("进入 Alpha 失败，请稍后再试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  function continueCurrentFamily() {
    router.push("/parent/children");
  }

  function restartAlphaFamily() {
    clearStoredAlphaParentId();
    window.dispatchEvent(new Event(ALPHA_PARENT_STORAGE_EVENT));
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-3xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
        <p className="text-sm font-semibold text-[var(--wen-muted)]">Alpha Entry</p>
        <h1 className="mt-3 text-3xl font-bold">小文星球 WenLingo</h1>

        {storedParentId ? (
          <div className="mt-6 rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-4">
            <p className="font-semibold">已经找到这个浏览器里的 Alpha 家庭。</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={continueCurrentFamily}
                className="rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white"
              >
                继续使用当前 Alpha 家庭
              </button>
              <button
                type="button"
                onClick={restartAlphaFamily}
                className="rounded-lg border border-[var(--wen-border)] bg-white px-5 py-3 font-semibold"
              >
                重新创建 Alpha 家庭
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="mt-6 space-y-4 text-[var(--wen-muted)]">
              <p>这是小文星球 WenLingo 的小范围 Alpha 内测。</p>
              <p>
                系统会保存孩子的昵称、年级、句子改写、短写作内容、AI
                反馈、能力变化和使用记录，用于生成学习反馈和改进产品。
              </p>
              <p>
                请不要填写孩子的真实姓名、学校、住址、电话、出生日期、照片或其他敏感信息。
              </p>
              <p>孩子的写作内容可能会发送给 AI 服务，用于生成学习反馈。</p>
              <p>继续使用表示家长同意参与本次内测。</p>
            </div>
            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <label className="block font-semibold">
                家长怎么称呼？
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  maxLength={40}
                  className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                />
              </label>
              <button
                type="submit"
                disabled={isSubmitting}
                className="rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                继续使用 Alpha
              </button>
            </form>
            {error ? (
              <p role="alert" className="mt-4 text-sm font-semibold text-red-600">
                {error}
              </p>
            ) : null}
          </>
        )}
      </section>
    </main>
  );
}
