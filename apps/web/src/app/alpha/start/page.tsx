"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import type { FormEvent } from "react";
import {
  createAlphaParent,
  getMyAlphaChildren,
  recordAlphaEvent,
  validateAlphaInvite,
} from "../../../lib/api";
import {
  clearStoredAlphaParentId,
  getStoredAlphaParentId,
} from "../../../lib/alphaParent";
import { getStoredAlphaSessionId } from "../../../lib/alphaSession";
import {
  AuthRequestError,
  getAuthSession,
  requestMagicCode,
  verifyMagicCode,
} from "../../../lib/authSession";
import type { AuthSession } from "../../../lib/types";

const ALPHA_PARENT_STORAGE_EVENT = "wenlingo-alpha-parent-storage";
const rawApiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
const API_BASE_URL = rawApiBaseUrl === "/api" ? "" : rawApiBaseUrl;
const DISABLED_ACCOUNT_MESSAGE = "账号暂不可用，请联系邀请人。";
const UNLINKED_ACCOUNT_MESSAGE = "这个邮箱还没有 Alpha 家庭，请使用邀请码创建。";
type EntryMode = "create_family" | "existing_account";
type AlphaStartAuthState =
  | "enter_email"
  | "enter_code"
  | "verifying_code"
  | "code_error"
  | "session_unavailable"
  | "unlinked_account"
  | "disabled_account"
  | "authenticated_redirecting";

const SESSION_UNAVAILABLE_MESSAGE =
  "登录状态没有保存成功，请刷新后重新登录。";

function isDisabledAccountError(error: unknown): boolean {
  return (
    error instanceof AuthRequestError &&
    error.status === 403 &&
    error.detail === DISABLED_ACCOUNT_MESSAGE
  );
}

function linkedParentId(session: AuthSession): string | null {
  if (!session.authenticated) {
    return null;
  }
  return session.parent?.id ?? session.parent_id ?? null;
}

function subscribeToAlphaParentStorage(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(ALPHA_PARENT_STORAGE_EVENT, onStoreChange);

  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(ALPHA_PARENT_STORAGE_EVENT, onStoreChange);
  };
}

async function bindLegacyParent(legacyParentId: string) {
  const response = await fetch(`${API_BASE_URL}/api/alpha/legacy-parent-bind`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ legacy_parent_id: legacyParentId }),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<{
    parent: { id: string; display_name: string };
  }>;
}

export default function AlphaStartPage() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("Alpha 家长");
  const [entryMode, setEntryMode] = useState<EntryMode>("create_family");
  const [inviteCode, setInviteCode] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeRequested, setCodeRequested] = useState(false);
  const [authState, setAuthState] =
    useState<AlphaStartAuthState>("enter_email");
  const [alphaSessionId] = useState(() => getStoredAlphaSessionId());
  const storedParentId = useSyncExternalStore(
    subscribeToAlphaParentStorage,
    getStoredAlphaParentId,
    () => null,
  );
  const [authSession, setAuthSession] = useState<AuthSession | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [isRequestingCode, setIsRequestingCode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    recordAlphaEvent({
      event_type: "alpha_start_viewed",
      alpha_session_id: alphaSessionId,
      payload: { path: "/alpha/start", status: "viewed" },
    });
  }, [alphaSessionId]);

  useEffect(() => {
    let isMounted = true;

    getAuthSession()
      .then((session) => {
        if (!isMounted) {
          return;
        }
        if (linkedParentId(session)) {
          router.push("/parent/children");
          return;
        }
        setAuthSession(session);
        setIsAuthLoading(false);
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setAuthSession({ authenticated: false });
        setIsAuthLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [router]);

  const isLegacyMigration =
    Boolean(storedParentId) &&
    (authSession?.authenticated === false ||
      (authSession?.authenticated === true && !authSession.parent));
  const isVerifiedLegacyMigration =
    Boolean(storedParentId) &&
    authSession?.authenticated === true &&
    !authSession.parent;

  function resetRequestedCode() {
    setCodeRequested(false);
    setCode("");
  }

  function handleEmailChange(value: string) {
    setEmail(value);
    resetRequestedCode();
  }

  function handleInviteCodeChange(value: string) {
    setInviteCode(value);
    if (!isLegacyMigration) {
      resetRequestedCode();
    }
  }

  function switchEntryMode(nextMode: EntryMode) {
    setEntryMode(nextMode);
    resetRequestedCode();
    setError("");
  }

  async function finishLegacyBind() {
    if (!storedParentId) {
      return false;
    }

    await bindLegacyParent(storedParentId);
    router.push("/parent/children");
    return true;
  }

  async function recoverLinkedSessionAfterBindFailure() {
    try {
      const session = await getAuthSession();
      const parentId = linkedParentId(session);
      if (parentId) {
        router.push("/parent/children");
        return true;
      }
      if (session.authenticated) {
        setAuthSession(session);
      }
    } catch {
      // Fall through to the parent-children probe below.
    }

    try {
      await getMyAlphaChildren();
      router.push("/parent/children");
      return true;
    } catch {
      return false;
    }
  }

  async function handleRequestCode() {
    if (isRequestingCode) {
      return;
    }

    const trimmedEmail = email.trim();
    const trimmedInviteCode = inviteCode.trim();
    if (!trimmedEmail) {
      setError("请输入邮箱。");
      return;
    }
    if (
      !isLegacyMigration &&
      entryMode === "create_family" &&
      !trimmedInviteCode
    ) {
      setError("请输入内测邀请码。");
      return;
    }

    setIsRequestingCode(true);
    setError("");
    let inviteValidated = false;
    try {
      if (!isLegacyMigration && entryMode === "create_family") {
        await validateAlphaInvite({
          code: trimmedInviteCode,
          alpha_session_id: alphaSessionId,
        });
        inviteValidated = true;
      }
      await requestMagicCode({
        email: trimmedEmail,
        alpha_session_id: alphaSessionId,
      });
      setCodeRequested(true);
      setAuthState("enter_code");
    } catch {
      setError(
        isLegacyMigration
          ? "验证码发送失败，请稍后再试。"
          : entryMode === "existing_account" || inviteValidated
            ? "验证码发送失败，请稍后再试。"
            : "邀请码无效或已失效，请检查后再试。",
      );
    } finally {
      setIsRequestingCode(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    const trimmedEmail = email.trim();
    const trimmedCode = code.trim();
    const trimmedInviteCode = inviteCode.trim();
    if (!isVerifiedLegacyMigration && !trimmedEmail) {
      setError("请输入邮箱。");
      return;
    }

    if (isVerifiedLegacyMigration) {
      setIsSubmitting(true);
      setError("");
      try {
        await finishLegacyBind();
      } catch {
        if (await recoverLinkedSessionAfterBindFailure()) {
          return;
        }
        setError("绑定失败，请稍后再试。");
      } finally {
        setIsSubmitting(false);
      }
      return;
    }

    if (!trimmedCode) {
      setError("请输入 6 位验证码。");
      return;
    }

    setIsSubmitting(true);
    setError("");
    setAuthState("verifying_code");
    try {
      let verifiedSession: AuthSession;
      try {
        verifiedSession = await verifyMagicCode({
          email: trimmedEmail,
          code: trimmedCode,
        });
      } catch (error) {
        if (isDisabledAccountError(error)) {
          setAuthState("disabled_account");
          setError(DISABLED_ACCOUNT_MESSAGE);
          return;
        }
        setAuthState("code_error");
        setError("验证码不正确或已过期，请重新输入。");
        return;
      }

      const verifiedParentId = linkedParentId(verifiedSession);
      if (verifiedParentId) {
        let currentSession: AuthSession | null = null;
        try {
          currentSession = await getAuthSession();
        } catch {
          currentSession = null;
        }
        if (!currentSession || !linkedParentId(currentSession)) {
          setAuthState("session_unavailable");
          setError(SESSION_UNAVAILABLE_MESSAGE);
          return;
        }
        setAuthSession(currentSession);
        setAuthState("authenticated_redirecting");
        router.push("/parent/children");
        return;
      }

      if (entryMode === "existing_account") {
        setAuthState("unlinked_account");
        setError(UNLINKED_ACCOUNT_MESSAGE);
        return;
      }

      if (verifiedSession.authenticated) {
        setAuthSession(verifiedSession);
      }

      if (isLegacyMigration && storedParentId) {
        await finishLegacyBind();
        return;
      }

      if (!trimmedInviteCode) {
        setError("请输入内测邀请码。");
        return;
      }

      const response = await createAlphaParent({
        display_name: displayName,
        invite_code: trimmedInviteCode,
        alpha_session_id: alphaSessionId,
      });
      router.push(response.children_url);
    } catch (error) {
      if (isLegacyMigration && (await recoverLinkedSessionAfterBindFailure())) {
        return;
      }
      setError(
        isLegacyMigration
          ? "绑定失败，请稍后再试。"
          : "登录或创建失败，请检查后再试。",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function restartAlphaFamily() {
    clearStoredAlphaParentId();
    window.dispatchEvent(new Event(ALPHA_PARENT_STORAGE_EVENT));
    setCodeRequested(false);
    setCode("");
    setError("");
  }

  function switchFromStaleFamilyToExistingLogin() {
    clearStoredAlphaParentId();
    window.dispatchEvent(new Event(ALPHA_PARENT_STORAGE_EVENT));
    setEntryMode("existing_account");
    setCodeRequested(false);
    setCode("");
    setError("");
  }

  function renderSessionUnavailableRetry() {
    if (authState !== "session_unavailable") {
      return null;
    }

    return (
      <button
        className="mt-3 rounded-lg border border-red-200 px-4 py-2 text-sm font-bold text-red-700"
        type="button"
        onClick={() => {
          setAuthState("enter_email");
          setCodeRequested(false);
          setCode("");
          setError("");
        }}
      >
        重新登录
      </button>
    );
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-3xl rounded-lg border border-[var(--wen-border)] bg-white p-6 shadow-sm">
        <p className="text-sm font-semibold text-[var(--wen-muted)]">Alpha Entry</p>
        <h1 className="mt-3 text-3xl font-bold">小文星球 WenLingo</h1>

        {isAuthLoading ? (
          <p className="mt-6 text-[var(--wen-muted)]">正在准备 Alpha 入口...</p>
        ) : isLegacyMigration ? (
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div className="rounded-lg border border-[var(--wen-border)] bg-[var(--wen-bg)] p-4">
              <p className="font-semibold">绑定邮箱继续使用当前 Alpha 家庭</p>
            </div>
            {isVerifiedLegacyMigration ? null : (
              <>
                <label className="block font-semibold">
                  邮箱
                  <input
                    value={email}
                    onChange={(event) => handleEmailChange(event.target.value)}
                    type="email"
                    className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                  />
                </label>
                <button
                  type="button"
                  onClick={handleRequestCode}
                  disabled={isRequestingCode}
                  className="rounded-lg border border-[var(--wen-border)] bg-white px-5 py-3 font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                >
                  获取验证码
                </button>
                {codeRequested ? (
                  <label className="block font-semibold">
                    6 位验证码
                    <input
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                      inputMode="numeric"
                      maxLength={6}
                      className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                    />
                  </label>
                ) : null}
              </>
            )}
            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={
                  isSubmitting || (!isVerifiedLegacyMigration && !codeRequested)
                }
                className="rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                绑定并继续
              </button>
              <button
                type="button"
                onClick={restartAlphaFamily}
                className="rounded-lg border border-[var(--wen-border)] bg-white px-5 py-3 font-semibold"
              >
                重新创建 Alpha 家庭
              </button>
              <button
                type="button"
                onClick={switchFromStaleFamilyToExistingLogin}
                className="rounded-lg border border-[var(--wen-border)] bg-white px-5 py-3 font-semibold"
              >
                这不是我的家庭，使用已有账号登录
              </button>
            </div>
            {error ? (
              <div role="alert" className="text-sm font-semibold text-red-600">
                {error}
                {renderSessionUnavailableRetry()}
              </div>
            ) : null}
          </form>
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
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => switchEntryMode("create_family")}
                  className={
                    entryMode === "create_family"
                      ? "rounded-lg bg-[var(--wen-orange)] px-4 py-2 text-sm font-bold text-white"
                      : "rounded-lg border border-[var(--wen-border)] bg-white px-4 py-2 text-sm font-bold"
                  }
                >
                  创建 Alpha 家庭
                </button>
                <button
                  type="button"
                  onClick={() => switchEntryMode("existing_account")}
                  className={
                    entryMode === "existing_account"
                      ? "rounded-lg bg-[var(--wen-orange)] px-4 py-2 text-sm font-bold text-white"
                      : "rounded-lg border border-[var(--wen-border)] bg-white px-4 py-2 text-sm font-bold"
                  }
                >
                  已有账号登录
                </button>
              </div>
              {entryMode === "create_family" ? (
                <>
                  <label className="block font-semibold">
                    家长怎么称呼？
                    <input
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
                      maxLength={40}
                      className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                    />
                  </label>
                  <label className="block font-semibold">
                    内测邀请码
                    <input
                      value={inviteCode}
                      onChange={(event) => handleInviteCodeChange(event.target.value)}
                      maxLength={40}
                      className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                    />
                  </label>
                </>
              ) : null}
              <label className="block font-semibold">
                邮箱
                <input
                  value={email}
                  onChange={(event) => handleEmailChange(event.target.value)}
                  type="email"
                  className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                />
              </label>
              <button
                type="button"
                onClick={handleRequestCode}
                disabled={isRequestingCode}
                className="rounded-lg border border-[var(--wen-border)] bg-white px-5 py-3 font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              >
                获取验证码
              </button>
              {codeRequested ? (
                <label className="block font-semibold">
                  6 位验证码
                  <input
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    inputMode="numeric"
                    maxLength={6}
                    className="mt-2 w-full rounded-lg border border-[var(--wen-border)] p-3"
                  />
                </label>
              ) : null}
              <button
                type="submit"
                disabled={isSubmitting || !codeRequested}
                className="rounded-lg bg-[var(--wen-orange)] px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {entryMode === "existing_account" ? "登录 Alpha" : "继续使用 Alpha"}
              </button>
            </form>
            {error ? (
              <div role="alert" className="mt-4 text-sm font-semibold text-red-600">
                {error}
                {renderSessionUnavailableRetry()}
              </div>
            ) : null}
          </>
        )}
      </section>
    </main>
  );
}
