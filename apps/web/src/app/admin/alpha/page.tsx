"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  createAdminAlphaInvites,
  deleteAdminAlphaTestAccounts,
  disableAdminAlphaAccount,
  enableAdminAlphaAccount,
  getAdminAlphaAccounts,
  getAdminAlphaAccountSessions,
  getAdminAlphaAIUsage,
  getAdminAlphaFamily,
  getAdminAlphaOverview,
  revokeAdminAlphaAccountSession,
  revokeAllAdminAlphaAccountSessions,
  revokeAdminAlphaInvite,
} from "../../../lib/api";
import type {
  AdminAlphaAIUsageRow,
  AdminAlphaAccountRow,
  AdminAlphaAccountSessionsResponse,
  AdminAlphaFamilyDetail,
  AdminAlphaInviteCreateResponse,
  AdminAlphaOverviewRow,
} from "../../../lib/types";

const ADMIN_TOKEN_STORAGE_KEY = "wenlingo_alpha_admin_token";

function formatReactionCounts(counts: Record<string, number>): string {
  const entries = Object.entries(counts);
  if (entries.length === 0) {
    return "none";
  }
  return entries.map(([reaction, count]) => `${reaction}: ${count}`).join(", ");
}

function formatAccountStatus(row: AdminAlphaOverviewRow): string {
  return row.account_linked ? "Account linked" : "No account";
}

function formatPhoneStatus(row: AdminAlphaOverviewRow): string {
  return row.phone_bound ? "Phone bound" : "Phone not bound";
}

function canRevokeInvite(row: AdminAlphaOverviewRow): boolean {
  return row.invite_status === "issued" && !row.parent_id;
}

export default function AdminAlphaPage() {
  const [token, setToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [families, setFamilies] = useState<AdminAlphaOverviewRow[]>([]);
  const [accounts, setAccounts] = useState<AdminAlphaAccountRow[]>([]);
  const [usageRows, setUsageRows] = useState<AdminAlphaAIUsageRow[]>([]);
  const [pricingConfigured, setPricingConfigured] = useState(false);
  const [showRevokedInvites, setShowRevokedInvites] = useState(false);
  const [generatedInvites, setGeneratedInvites] = useState<
    AdminAlphaInviteCreateResponse["invites"]
  >([]);
  const [inviteCount, setInviteCount] = useState(1);
  const [inviteLabelPrefix, setInviteLabelPrefix] = useState("Alpha QA");
  const [inviteNote, setInviteNote] = useState("");
  const [selectedParentId, setSelectedParentId] = useState<string | null>(null);
  const [familyDetail, setFamilyDetail] = useState<AdminAlphaFamilyDetail | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [pendingAccountActionIds, setPendingAccountActionIds] = useState<
    string[]
  >([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [selectedSessionAccountId, setSelectedSessionAccountId] = useState<
    string | null
  >(null);
  const [accountSessions, setAccountSessions] =
    useState<AdminAlphaAccountSessionsResponse | null>(null);
  const [confirmRevokeAllAccountId, setConfirmRevokeAllAccountId] = useState<
    string | null
  >(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [isDeletingTestAccounts, setIsDeletingTestAccounts] = useState(false);
  const [notice, setNotice] = useState("");
  const hasSkippedRevokedReloadRef = useRef(false);
  const revokedRefreshRequestIdRef = useRef(0);
  const accountSessionRequestIdRef = useRef(0);

  const clearAdminSession = useCallback((message: string) => {
    revokedRefreshRequestIdRef.current += 1;
    accountSessionRequestIdRef.current += 1;
    setError(message);
    setToken("");
    window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
    setFamilies([]);
    setAccounts([]);
    setUsageRows([]);
    setPricingConfigured(false);
    setGeneratedInvites([]);
    setSelectedParentId(null);
    setFamilyDetail(null);
    setPendingAccountActionIds([]);
    setSelectedAccountIds([]);
    setSelectedSessionAccountId(null);
    setAccountSessions(null);
    setConfirmRevokeAllAccountId(null);
    setDeleteConfirmation("");
    setNotice("");
    setIsDeletingTestAccounts(false);
  }, []);

  const loadOverview = useCallback(
    async (
      nextToken: string,
      includeRevokedInvites: boolean,
    ): Promise<boolean> => {
      setIsLoading(true);
      setError("");
      try {
        const [overviewResponse, accountResponse, usageResponse] =
          await Promise.all([
            getAdminAlphaOverview(nextToken, includeRevokedInvites),
            getAdminAlphaAccounts(nextToken),
            getAdminAlphaAIUsage(nextToken),
          ]);
        setFamilies(overviewResponse.families);
        setAccounts(accountResponse.accounts);
        setUsageRows(usageResponse.usage);
        setPricingConfigured(usageResponse.pricing_configured);
        setToken(nextToken);
        window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, nextToken);
        return true;
      } catch {
        clearAdminSession("Token invalid or admin overview unavailable.");
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [clearAdminSession],
  );

  useEffect(() => {
    const storedToken = window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
    if (!storedToken) {
      return;
    }
    let active = true;
    queueMicrotask(() => {
      if (active) {
        void loadOverview(storedToken, false);
      }
    });
    return () => {
      active = false;
    };
  }, [loadOverview]);

  useEffect(() => {
    if (!token) {
      hasSkippedRevokedReloadRef.current = false;
      revokedRefreshRequestIdRef.current += 1;
      return;
    }
    if (!hasSkippedRevokedReloadRef.current) {
      hasSkippedRevokedReloadRef.current = true;
      return;
    }
    const requestId = revokedRefreshRequestIdRef.current + 1;
    revokedRefreshRequestIdRef.current = requestId;
    setError("");
    getAdminAlphaOverview(token, showRevokedInvites)
      .then((response) => {
        if (revokedRefreshRequestIdRef.current !== requestId) {
          return;
        }
        setFamilies(response.families);
        setError("");
      })
      .catch(() => {
        if (revokedRefreshRequestIdRef.current !== requestId) {
          return;
        }
        clearAdminSession("Admin overview unavailable.");
      });
  }, [clearAdminSession, showRevokedInvites, token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextToken = tokenInput.trim();
    if (!nextToken) {
      setError("Token invalid or admin overview unavailable.");
      return;
    }
    await loadOverview(nextToken, showRevokedInvites);
  }

  async function refreshAccounts() {
    if (!token) {
      return;
    }
    const response = await getAdminAlphaAccounts(token);
    setAccounts(response.accounts);
  }

  async function handleLoadAccountSessions(accountId: string) {
    if (!token) {
      return;
    }
    const requestId = accountSessionRequestIdRef.current + 1;
    accountSessionRequestIdRef.current = requestId;
    setError("");
    setSelectedSessionAccountId(accountId);
    setAccountSessions(null);
    setConfirmRevokeAllAccountId(null);
    try {
      const response = await getAdminAlphaAccountSessions(token, accountId);
      if (accountSessionRequestIdRef.current !== requestId) {
        return;
      }
      setAccountSessions(response);
    } catch {
      if (accountSessionRequestIdRef.current !== requestId) {
        return;
      }
      setError("Account sessions unavailable.");
    }
  }

  async function handleRevokeAccountSession(accountId: string, sessionId: string) {
    if (!token) {
      return;
    }
    setError("");
    try {
      await revokeAdminAlphaAccountSession(token, accountId, sessionId);
      await handleLoadAccountSessions(accountId);
      await refreshAccounts();
    } catch {
      setError("Session revoke failed.");
    }
  }

  async function handleRevokeAllAccountSessions(accountId: string) {
    if (!token) {
      return;
    }
    setError("");
    try {
      await revokeAllAdminAlphaAccountSessions(token, accountId);
      setConfirmRevokeAllAccountId(null);
      await handleLoadAccountSessions(accountId);
      await refreshAccounts();
    } catch {
      setError("Session revoke failed.");
    }
  }

  async function handleGenerateInvites(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }
    setError("");
    try {
      const response = await createAdminAlphaInvites(token, {
        count: inviteCount,
        label_prefix: inviteLabelPrefix,
        issued_to_note: inviteNote,
      });
      setGeneratedInvites(response.invites);
      await loadOverview(token, showRevokedInvites);
    } catch {
      setError("Invite generation failed.");
    }
  }

  async function handleAccountAction(account: AdminAlphaAccountRow) {
    if (!token) {
      return;
    }
    if (pendingAccountActionIds.includes(account.account_id)) {
      return;
    }
    setPendingAccountActionIds((currentAccountIds) =>
      currentAccountIds.includes(account.account_id)
        ? currentAccountIds
        : [...currentAccountIds, account.account_id],
    );
    setError("");
    setNotice("");
    try {
      const nextStatus = account.status === "disabled" ? "active" : "disabled";
      if (account.status === "disabled") {
        await enableAdminAlphaAccount(token, account.account_id);
      } else {
        await disableAdminAlphaAccount(token, account.account_id);
      }
      await refreshAccounts();
      setAccounts((currentAccounts) =>
        currentAccounts.map((currentAccount) =>
          currentAccount.account_id === account.account_id
            ? { ...currentAccount, status: nextStatus }
            : currentAccount,
        ),
      );
    } catch {
      setError("Account action failed.");
    } finally {
      setPendingAccountActionIds((currentAccountIds) =>
        currentAccountIds.filter(
          (currentAccountId) => currentAccountId !== account.account_id,
        ),
      );
    }
  }

  function toggleSelectedAccount(accountId: string) {
    setSelectedAccountIds((currentAccountIds) =>
      currentAccountIds.includes(accountId)
        ? currentAccountIds.filter((currentAccountId) => currentAccountId !== accountId)
        : [...currentAccountIds, accountId],
    );
  }

  async function handleDeleteTestAccounts() {
    if (
      !token ||
      selectedAccountIds.length === 0 ||
      deleteConfirmation !== "DELETE TEST ACCOUNTS"
    ) {
      return;
    }
    setIsDeletingTestAccounts(true);
    setError("");
    setNotice("");
    try {
      const response = await deleteAdminAlphaTestAccounts(token, {
        account_ids: selectedAccountIds,
        confirm: deleteConfirmation,
      });
      setSelectedAccountIds([]);
      setDeleteConfirmation("");
      setNotice(
        `Deleted ${response.deleted_count} test account${
          response.deleted_count === 1 ? "" : "s"
        }.`,
      );
      await loadOverview(token, showRevokedInvites);
    } catch {
      setError("Test account delete failed.");
    } finally {
      setIsDeletingTestAccounts(false);
    }
  }

  async function handleRevokeInvite(row: AdminAlphaOverviewRow) {
    if (!token) {
      return;
    }
    setError("");
    try {
      await revokeAdminAlphaInvite(token, row.invite_id);
      await loadOverview(token, showRevokedInvites);
    } catch {
      setError("Invite revoke failed.");
    }
  }

  async function selectFamily(row: AdminAlphaOverviewRow) {
    if (!row.parent_id || !token) {
      return;
    }
    setSelectedParentId(row.parent_id);
    setFamilyDetail(null);
    setError("");
    try {
      setFamilyDetail(await getAdminAlphaFamily(token, row.parent_id));
    } catch {
      setError("Family timeline unavailable.");
    }
  }

  function renderOverviewCells(row: AdminAlphaOverviewRow) {
    return (
      <>
        <span>
          <strong>{row.invite_label}</strong>
          <span className="mt-1 block text-xs text-[var(--wen-muted)]">
            {row.invite_status}
          </span>
        </span>
        <span>{row.parent_display_name ?? "Unclaimed"}</span>
        <span>
          <strong>{formatAccountStatus(row)}</strong>
          <span className="mt-1 block text-xs text-[var(--wen-muted)]">
            {row.account_email_masked ?? "No email"}
          </span>
          <span className="mt-1 block text-xs text-[var(--wen-muted)]">
            {formatPhoneStatus(row)}
          </span>
          <span className="mt-1 block text-xs text-[var(--wen-muted)]">
            {row.last_login_at ?? "No last login"}
          </span>
        </span>
        <span>{row.funnel_stage}</span>
        <span>{row.child_count} child</span>
        <span>{formatReactionCounts(row.reaction_counts)}</span>
        <span>{row.latest_parent_feedback ?? "none"}</span>
        <span>{row.last_event_at ?? "none"}</span>
      </>
    );
  }

  const loadedSessionAccountId = accountSessions?.account.account_id ?? null;

  return (
    <main className="min-h-screen bg-[var(--wen-bg)] px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-2 border-b border-[var(--wen-border)] pb-5">
          <p className="text-sm font-semibold text-[var(--wen-muted)]">
            Read-only
          </p>
          <h1 className="text-3xl font-bold">Admin Alpha Lite</h1>
        </div>

        {!token ? (
          <form
            onSubmit={handleSubmit}
            className="mt-6 flex max-w-md flex-col gap-3 rounded-lg border border-[var(--wen-border)] bg-white p-5"
          >
            <label className="text-sm font-semibold" htmlFor="admin-alpha-token">
              Admin token
            </label>
            <input
              id="admin-alpha-token"
              type="password"
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
              className="rounded-lg border border-[var(--wen-border)] px-3 py-2"
            />
            <button
              type="submit"
              className="w-fit rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
            >
              进入
            </button>
          </form>
        ) : null}

        {error ? (
          <p
            role="alert"
            aria-label="Admin alpha error"
            className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 font-semibold text-red-700"
          >
            {error}
          </p>
        ) : null}

        {notice ? (
          <p className="mt-5 rounded-lg border border-green-200 bg-green-50 p-4 font-semibold text-green-800">
            {notice}
          </p>
        ) : null}

        {token ? (
          <div className="mt-6">
            {isLoading ? (
              <p className="rounded-lg border border-[var(--wen-border)] bg-white p-4 text-[var(--wen-muted)]">
                Loading overview...
              </p>
            ) : null}

            <section
              aria-labelledby="invite-management-heading"
              className="mb-6 rounded-lg border border-[var(--wen-border)] bg-white p-5"
            >
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 id="invite-management-heading" className="text-xl font-bold">
                  邀请管理
                </h2>
                <label className="inline-flex items-center gap-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={showRevokedInvites}
                    onChange={(event) =>
                      setShowRevokedInvites(event.target.checked)
                    }
                  />
                  显示已撤销邀请码
                </label>
              </div>
              <div className="flex flex-wrap items-start justify-between gap-6">
                <form
                  onSubmit={handleGenerateInvites}
                  className="grid min-w-64 flex-1 gap-3 sm:grid-cols-[8rem_1fr_1fr_auto]"
                >
                  <label className="flex flex-col gap-1 text-sm font-semibold">
                    Invite count
                    <input
                      type="number"
                      min={1}
                      value={inviteCount}
                      onChange={(event) =>
                        setInviteCount(Number(event.target.value))
                      }
                      className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm font-semibold">
                    Label prefix
                    <input
                      type="text"
                      value={inviteLabelPrefix}
                      onChange={(event) =>
                        setInviteLabelPrefix(event.target.value)
                      }
                      className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm font-semibold">
                    Issued note
                    <input
                      type="text"
                      value={inviteNote}
                      onChange={(event) => setInviteNote(event.target.value)}
                      className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                    />
                  </label>
                  <button
                    type="submit"
                    className="self-end rounded-lg bg-[var(--wen-orange)] px-4 py-2 font-semibold text-white"
                  >
                    生成邀请码
                  </button>
                </form>
              </div>

              {generatedInvites.length > 0 ? (
                <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-4">
                  <p className="font-semibold text-amber-900">
                    这些邀请码只显示一次。关闭页面后无法再次查看，请立即复制并安全保存。
                  </p>
                  <ul className="mt-3 grid gap-2">
                    {generatedInvites.map((invite) => (
                      <li
                        key={invite.invite_id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-white px-3 py-2 text-sm"
                      >
                        <span className="font-semibold">{invite.label}</span>
                        <code>{invite.raw_code}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

            </section>

            <section
              aria-labelledby="account-management-heading"
              className="mb-6 rounded-lg border border-[var(--wen-border)] bg-white p-5"
            >
              <h2 id="account-management-heading" className="text-xl font-bold">
                账号管理
              </h2>
              <div className="mt-5 grid gap-3">
                {accounts.map((account) => {
                  const isPending =
                    pendingAccountActionIds.includes(account.account_id);
                  const isDisabledAccount = account.status === "disabled";
                  return (
                    <div
                      key={account.account_id}
                      className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--wen-border)] pt-3 text-sm"
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          aria-label={`Select ${account.email_masked}`}
                          checked={selectedAccountIds.includes(
                            account.account_id,
                          )}
                          onChange={() =>
                            toggleSelectedAccount(account.account_id)
                          }
                        />
                        <div>
                          <strong>{account.email_masked}</strong>
                          <span className="ml-3 text-[var(--wen-muted)]">
                            {account.active_session_count} active session
                            {account.active_session_count === 1 ? "" : "s"}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            void handleLoadAccountSessions(account.account_id)
                          }
                          className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold"
                        >
                          查看 sessions
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleAccountAction(account)}
                          disabled={isPending}
                          className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold disabled:cursor-not-allowed disabled:text-[var(--wen-muted)]"
                        >
                          {isPending
                            ? isDisabledAccount
                              ? "Enabling..."
                              : "Disabling..."
                            : isDisabledAccount
                              ? "Enable account"
                              : "Disable account"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {accountSessions && loadedSessionAccountId ? (
                <section aria-label="账号 sessions" className="mt-4">
                  <h3 className="font-bold">Active sessions</h3>
                  {accountSessions.sessions.length === 0 ? (
                    <p className="mt-3 text-sm text-[var(--wen-muted)]">
                      没有 active sessions。
                    </p>
                  ) : (
                    <div className="mt-3 overflow-x-auto">
                      <table
                        aria-label="Account sessions"
                        className="min-w-full text-sm"
                      >
                        <thead>
                          <tr className="border-b border-[var(--wen-border)] bg-[var(--wen-bg)] text-left text-xs font-bold uppercase text-[var(--wen-muted)]">
                            <th className="px-3 py-2">Session</th>
                            <th className="px-3 py-2">Created</th>
                            <th className="px-3 py-2">Last seen</th>
                            <th className="px-3 py-2">Expires</th>
                            <th className="px-3 py-2">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {accountSessions.sessions.map((parentSession) => (
                            <tr
                              key={parentSession.session_id}
                              className="border-b border-[var(--wen-border)] last:border-b-0"
                            >
                              <td className="px-3 py-2">
                                {parentSession.session_id}
                              </td>
                              <td className="px-3 py-2">
                                {parentSession.created_at}
                              </td>
                              <td className="px-3 py-2">
                                {parentSession.last_seen_at}
                              </td>
                              <td className="px-3 py-2">
                                {parentSession.expires_at}
                              </td>
                              <td className="px-3 py-2">
                                <button
                                  type="button"
                                  onClick={() =>
                                    void handleRevokeAccountSession(
                                      loadedSessionAccountId,
                                      parentSession.session_id,
                                    )
                                  }
                                  className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold"
                                >
                                  撤销 session
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {confirmRevokeAllAccountId === loadedSessionAccountId ? (
                    <div
                      role="alert"
                      className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4"
                    >
                      <p className="font-semibold text-amber-900">
                        这会让该家长账号的所有设备重新登录。
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            void handleRevokeAllAccountSessions(
                              loadedSessionAccountId,
                            )
                          }
                          className="rounded-lg border border-red-200 px-3 py-2 font-semibold text-red-700"
                        >
                          确认撤销全部 sessions
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmRevokeAllAccountId(null)}
                          className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold"
                        >
                          取消
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        setConfirmRevokeAllAccountId(loadedSessionAccountId)
                      }
                      className="mt-4 rounded-lg border border-red-200 px-3 py-2 font-semibold text-red-700"
                    >
                      撤销全部 sessions
                    </button>
                  )}
                </section>
              ) : null}

              <div className="mt-5 grid gap-3 border-t border-[var(--wen-border)] pt-4">
                <p className="text-sm text-[var(--wen-muted)]">
                  Permanently delete selected Dev/QA test accounts only.
                </p>
                <label className="flex max-w-md flex-col gap-1 text-sm font-semibold">
                  Delete confirmation
                  <input
                    type="text"
                    value={deleteConfirmation}
                    onChange={(event) =>
                      setDeleteConfirmation(event.target.value)
                    }
                    className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-normal"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => void handleDeleteTestAccounts()}
                  disabled={
                    isDeletingTestAccounts ||
                    selectedAccountIds.length === 0 ||
                    deleteConfirmation !== "DELETE TEST ACCOUNTS"
                  }
                  className="w-fit rounded-lg border border-red-200 px-3 py-2 font-semibold text-red-700 disabled:cursor-not-allowed disabled:text-[var(--wen-muted)]"
                >
                  {isDeletingTestAccounts
                    ? "Deleting..."
                    : "Delete selected test accounts"}
                </button>
              </div>
            </section>

            <section
              aria-labelledby="alpha-overview-heading"
              className="mb-6"
            >
              <h2 id="alpha-overview-heading" className="mb-3 text-xl font-bold">
                Alpha 总览
              </h2>
              <div className="overflow-hidden rounded-lg border border-[var(--wen-border)] bg-white">
                <div className="grid grid-cols-[1.2fr_1fr_1.3fr_1fr_0.7fr_1.2fr_1fr_1.5fr_auto] gap-3 border-b border-[var(--wen-border)] bg-[var(--wen-bg)] px-4 py-3 text-xs font-bold uppercase text-[var(--wen-muted)]">
                  <span>Invite</span>
                  <span>Family</span>
                  <span>Account</span>
                  <span>Funnel</span>
                  <span>Children</span>
                  <span>Reactions</span>
                  <span>Feedback</span>
                  <span>Last activity</span>
                  <span>Actions</span>
                </div>
                {families.map((row) =>
                  canRevokeInvite(row) ? (
                    <div
                      key={row.invite_id}
                      className="grid w-full grid-cols-[1.2fr_1fr_1.3fr_1fr_0.7fr_1.2fr_1fr_1.5fr_auto] gap-3 border-b border-[var(--wen-border)] px-4 py-3 text-left text-sm last:border-b-0"
                    >
                      {renderOverviewCells(row)}
                      <span>
                        <button
                          type="button"
                          onClick={() => void handleRevokeInvite(row)}
                          className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold"
                        >
                          Revoke invite
                        </button>
                      </span>
                    </div>
                  ) : (
                    <button
                      key={row.invite_id}
                      type="button"
                      onClick={() => void selectFamily(row)}
                      disabled={!row.parent_id}
                      className="grid w-full grid-cols-[1.2fr_1fr_1.3fr_1fr_0.7fr_1.2fr_1fr_1.5fr_auto] gap-3 border-b border-[var(--wen-border)] px-4 py-3 text-left text-sm last:border-b-0 disabled:cursor-not-allowed disabled:text-[var(--wen-muted)]"
                    >
                      {renderOverviewCells(row)}
                      <span />
                    </button>
                  ),
                )}
              </div>
            </section>

            <section
              aria-labelledby="ai-usage-heading"
              className="rounded-lg border border-[var(--wen-border)] bg-white p-5"
            >
              <h2 id="ai-usage-heading" className="text-xl font-bold">
                AI 使用量
              </h2>
              {usageRows.length > 0 ? (
                <div className="mt-4 overflow-x-auto">
                  <table aria-label="AI usage" className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--wen-border)] bg-[var(--wen-bg)] text-left text-xs font-bold uppercase text-[var(--wen-muted)]">
                        <th className="px-3 py-2">Date</th>
                        <th className="px-3 py-2">Task</th>
                        <th className="px-3 py-2">Provider</th>
                        <th className="px-3 py-2">Model</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Calls</th>
                        <th className="px-3 py-2">Success</th>
                        <th className="px-3 py-2">Fallback</th>
                        <th className="px-3 py-2">Failures</th>
                        <th className="px-3 py-2">Limit hits</th>
                        <th className="px-3 py-2">Tokens</th>
                        <th className="px-3 py-2">Cost</th>
                        <th className="px-3 py-2">Avg latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usageRows.map((row) => (
                        <tr
                          key={`${row.date}:${row.task_type}:${row.provider}:${row.model}:${row.final_status}`}
                          className="border-b border-[var(--wen-border)] last:border-b-0"
                        >
                          <td className="px-3 py-2">{row.date}</td>
                          <td className="px-3 py-2">{row.task_type}</td>
                          <td className="px-3 py-2">{row.provider}</td>
                          <td className="px-3 py-2">{row.model}</td>
                          <td className="px-3 py-2">{row.final_status}</td>
                          <td className="px-3 py-2">{row.call_count}</td>
                          <td className="px-3 py-2">{row.success_count}</td>
                          <td className="px-3 py-2">
                            {row.fallback_success_count} / local{" "}
                            {row.deterministic_fallback_count}
                          </td>
                          <td className="px-3 py-2">{row.failure_count}</td>
                          <td className="px-3 py-2">
                            {row.daily_limit_hit_count}
                          </td>
                          <td className="px-3 py-2">{row.total_tokens}</td>
                          <td className="px-3 py-2">
                            {pricingConfigured
                              ? `$${row.estimated_cost.toFixed(6)}`
                              : "未配置价格"}
                          </td>
                          <td className="px-3 py-2">
                            {row.avg_latency_ms}ms
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mt-4 text-sm text-[var(--wen-muted)]">
                  No AI usage yet.
                </p>
              )}
            </section>
          </div>
        ) : null}

        {selectedParentId && familyDetail ? (
          <section className="mt-6 border-t border-[var(--wen-border)] pt-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-[var(--wen-muted)]">
                  {familyDetail.parent.id}
                </p>
                <h2 className="text-2xl font-bold">
                  {familyDetail.parent.display_name}
                </h2>
              </div>
              <p className="text-sm text-[var(--wen-muted)]">
                {familyDetail.children.length} child ·{" "}
                {formatReactionCounts(familyDetail.reaction_counts)}
              </p>
            </div>
            <ol aria-label="Family timeline" className="mt-5 space-y-3">
              {familyDetail.events.map((event) => (
                <li
                  key={event.id}
                  className="rounded-lg border border-[var(--wen-border)] bg-white p-4"
                >
                  <div className="flex flex-wrap justify-between gap-3">
                    <strong>{event.event_type}</strong>
                    <span className="text-sm text-[var(--wen-muted)]">
                      {event.created_at}
                    </span>
                  </div>
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-[var(--wen-bg)] p-3 text-xs">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </li>
              ))}
            </ol>
          </section>
        ) : null}
      </section>
    </main>
  );
}
