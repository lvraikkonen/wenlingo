"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  createAdminAlphaInvites,
  disableAdminAlphaAccount,
  enableAdminAlphaAccount,
  getAdminAlphaAccounts,
  getAdminAlphaFamily,
  getAdminAlphaOverview,
  revokeAdminAlphaInvite,
} from "../../../lib/api";
import type {
  AdminAlphaAccountRow,
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

  useEffect(() => {
    const storedToken = window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
    if (!storedToken) {
      return;
    }
    void loadOverview(storedToken);
  }, []);

  async function loadOverview(nextToken: string): Promise<boolean> {
    setIsLoading(true);
    setError("");
    try {
      const [overviewResponse, accountResponse] = await Promise.all([
        getAdminAlphaOverview(nextToken),
        getAdminAlphaAccounts(nextToken),
      ]);
      setFamilies(overviewResponse.families);
      setAccounts(accountResponse.accounts);
      setToken(nextToken);
      window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, nextToken);
      return true;
    } catch {
      setError("Token invalid or admin overview unavailable.");
      setToken("");
      window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
      setFamilies([]);
      setAccounts([]);
      setGeneratedInvites([]);
      setFamilyDetail(null);
      return false;
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextToken = tokenInput.trim();
    if (!nextToken) {
      setError("Token invalid or admin overview unavailable.");
      return;
    }
    await loadOverview(nextToken);
  }

  async function refreshAccounts() {
    if (!token) {
      return;
    }
    const response = await getAdminAlphaAccounts(token);
    setAccounts(response.accounts);
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
      await loadOverview(token);
    } catch {
      setError("Invite generation failed.");
    }
  }

  async function handleAccountAction(account: AdminAlphaAccountRow) {
    if (!token) {
      return;
    }
    setError("");
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
    }
  }

  async function handleRevokeInvite(row: AdminAlphaOverviewRow) {
    if (!token) {
      return;
    }
    setError("");
    try {
      await revokeAdminAlphaInvite(token, row.invite_id);
      await loadOverview(token);
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

        {token ? (
          <div className="mt-6">
            {isLoading ? (
              <p className="rounded-lg border border-[var(--wen-border)] bg-white p-4 text-[var(--wen-muted)]">
                Loading overview...
              </p>
            ) : null}

            <section className="mb-6 rounded-lg border border-[var(--wen-border)] bg-white p-5">
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

              <div className="mt-5 grid gap-3">
                {accounts.map((account) => (
                  <div
                    key={account.account_id}
                    className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--wen-border)] pt-3 text-sm"
                  >
                    <div>
                      <strong>{account.email_masked}</strong>
                      <span className="ml-3 text-[var(--wen-muted)]">
                        {account.active_session_count} active session
                        {account.active_session_count === 1 ? "" : "s"}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleAccountAction(account)}
                      className="rounded-lg border border-[var(--wen-border)] px-3 py-2 font-semibold"
                    >
                      {account.status === "disabled"
                        ? "Enable account"
                        : "Disable account"}
                    </button>
                  </div>
                ))}
              </div>
            </section>

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
