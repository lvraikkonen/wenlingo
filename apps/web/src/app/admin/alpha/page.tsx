"use client";

import { FormEvent, useEffect, useState } from "react";
import { getAdminAlphaFamily, getAdminAlphaOverview } from "../../../lib/api";
import type {
  AdminAlphaFamilyDetail,
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

export default function AdminAlphaPage() {
  const [token, setToken] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [families, setFamilies] = useState<AdminAlphaOverviewRow[]>([]);
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
      const response = await getAdminAlphaOverview(nextToken);
      setFamilies(response.families);
      setToken(nextToken);
      window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, nextToken);
      return true;
    } catch {
      setError("Token invalid or admin overview unavailable.");
      setToken("");
      window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
      setFamilies([]);
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

            <div className="overflow-hidden rounded-lg border border-[var(--wen-border)] bg-white">
              <div className="grid grid-cols-[1.2fr_1fr_1fr_0.7fr_1.2fr_1fr_1.5fr] gap-3 border-b border-[var(--wen-border)] bg-[var(--wen-bg)] px-4 py-3 text-xs font-bold uppercase text-[var(--wen-muted)]">
                <span>Invite</span>
                <span>Family</span>
                <span>Funnel</span>
                <span>Children</span>
                <span>Reactions</span>
                <span>Feedback</span>
                <span>Last activity</span>
              </div>
              {families.map((row) => (
                <button
                  key={row.invite_id}
                  type="button"
                  onClick={() => void selectFamily(row)}
                  disabled={!row.parent_id}
                  className="grid w-full grid-cols-[1.2fr_1fr_1fr_0.7fr_1.2fr_1fr_1.5fr] gap-3 border-b border-[var(--wen-border)] px-4 py-3 text-left text-sm last:border-b-0 disabled:cursor-not-allowed disabled:text-[var(--wen-muted)]"
                >
                  <span>
                    <strong>{row.invite_label}</strong>
                    <span className="mt-1 block text-xs text-[var(--wen-muted)]">
                      {row.invite_status}
                    </span>
                  </span>
                  <span>{row.parent_display_name ?? "Unclaimed"}</span>
                  <span>{row.funnel_stage}</span>
                  <span>{row.child_count} child</span>
                  <span>{formatReactionCounts(row.reaction_counts)}</span>
                  <span>{row.latest_parent_feedback ?? "none"}</span>
                  <span>{row.last_event_at ?? "none"}</span>
                </button>
              ))}
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
