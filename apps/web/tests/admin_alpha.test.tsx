import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import AdminAlphaPage from "../src/app/admin/alpha/page";

const apiMocks = vi.hoisted(() => ({
  getAdminAlphaOverview: vi.fn(),
  getAdminAlphaFamily: vi.fn(),
  getAdminAlphaAccounts: vi.fn(),
  getAdminAlphaAIUsage: vi.fn(),
  createAdminAlphaInvites: vi.fn(),
  revokeAdminAlphaInvite: vi.fn(),
  disableAdminAlphaAccount: vi.fn(),
  enableAdminAlphaAccount: vi.fn(),
  deleteAdminAlphaTestAccounts: vi.fn(),
}));

vi.mock("../src/lib/api", () => ({
  getAdminAlphaOverview: apiMocks.getAdminAlphaOverview,
  getAdminAlphaFamily: apiMocks.getAdminAlphaFamily,
  getAdminAlphaAccounts: apiMocks.getAdminAlphaAccounts,
  getAdminAlphaAIUsage: apiMocks.getAdminAlphaAIUsage,
  createAdminAlphaInvites: apiMocks.createAdminAlphaInvites,
  revokeAdminAlphaInvite: apiMocks.revokeAdminAlphaInvite,
  disableAdminAlphaAccount: apiMocks.disableAdminAlphaAccount,
  enableAdminAlphaAccount: apiMocks.enableAdminAlphaAccount,
  deleteAdminAlphaTestAccounts: apiMocks.deleteAdminAlphaTestAccounts,
}));

const overview = {
  families: [
    {
      invite_id: "invite-1",
      invite_label: "家庭 01",
      invite_status: "consumed",
      parent_id: "parent-1",
      parent_display_name: "小星家长",
      child_count: 1,
      funnel_stage: "summary_viewed",
      assessment_completed_count: 1,
      summary_viewed: true,
      reaction_counts: { positive: 2, negative: 1 },
      latest_parent_feedback: "helpful",
      last_event_at: "2026-05-29T10:00:00+08:00",
      account_linked: true,
      account_email_masked: "pa***@example.com",
      phone_bound: true,
      last_login_at: "2026-05-29T09:30:00+08:00",
    },
  ],
};

const familyDetail = {
  parent: { id: "parent-1", display_name: "小星家长" },
  children: [{ id: "child-1", grade_label: "四年级" }],
  events: [
    {
      id: "event-1",
      event_type: "alpha_parent_created",
      created_at: "2026-05-29T09:00:00+08:00",
      payload: { status: "created" },
    },
    {
      id: "event-2",
      event_type: "summary_viewed",
      created_at: "2026-05-29T10:00:00+08:00",
      payload: { summary_viewed: true, status: "viewed" },
    },
  ],
  reaction_counts: { positive: 2, negative: 1 },
  parent_feedback: [{ student_id: "child-1", usefulness: "helpful" }],
};

beforeEach(() => {
  window.sessionStorage.clear();
  apiMocks.getAdminAlphaOverview.mockResolvedValue(overview);
  apiMocks.getAdminAlphaFamily.mockResolvedValue(familyDetail);
  apiMocks.getAdminAlphaAccounts.mockResolvedValue({
    accounts: [
      {
        account_id: "account-1",
        email_masked: "pa***@example.com",
        status: "active",
        parent_id: "parent-1",
        parent_display_name: "小星家长",
        children_count: 1,
        last_login_at: "2026-05-29T09:30:00+08:00",
        active_session_count: 1,
        created_at: "2026-05-28T09:30:00+08:00",
      },
    ],
  });
  apiMocks.getAdminAlphaAIUsage.mockResolvedValue({ usage: [] });
  apiMocks.createAdminAlphaInvites.mockResolvedValue({
    invites: [
      {
        invite_id: "invite-new",
        label: "Alpha QA 01",
        status: "issued",
        raw_code: "ALPHA-NEWCODE",
      },
    ],
  });
  apiMocks.revokeAdminAlphaInvite.mockResolvedValue({
    invite: {
      invite_id: "invite-new",
      label: "Alpha QA 01",
      status: "revoked",
    },
  });
  apiMocks.disableAdminAlphaAccount.mockResolvedValue({
    account: {
      account_id: "account-1",
      status: "disabled",
      revoked_session_count: 1,
    },
  });
  apiMocks.enableAdminAlphaAccount.mockResolvedValue({
    account: {
      account_id: "account-1",
      status: "active",
    },
  });
  apiMocks.deleteAdminAlphaTestAccounts.mockResolvedValue({
    deleted_count: 1,
    accounts: [
      {
        account_id: "account-1",
        email_masked: "pa***@example.com",
        parent_ids: ["parent-1"],
        child_count: 1,
        deleted_session_count: 0,
        deleted_invite_count: 1,
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("token gate renders before overview", () => {
  render(<AdminAlphaPage />);

  expect(screen.getByRole("heading", { name: "Admin Alpha Lite" })).toBeInTheDocument();
  expect(screen.getByLabelText("Admin token")).toBeInTheDocument();
  expect(apiMocks.getAdminAlphaOverview).not.toHaveBeenCalled();
});

test("submitting token stores it in sessionStorage", async () => {
  render(<AdminAlphaPage />);

  await userEvent.type(screen.getByLabelText("Admin token"), "secret");
  await userEvent.click(screen.getByRole("button", { name: "进入" }));

  await waitFor(() =>
    expect(apiMocks.getAdminAlphaOverview).toHaveBeenCalledWith("secret", false),
  );
  expect(window.sessionStorage.getItem("wenlingo_alpha_admin_token")).toBe("secret");
});

test("admin renders grouped sections and ai usage aggregates", async () => {
  apiMocks.getAdminAlphaAIUsage.mockResolvedValueOnce({
    usage: [
      {
        date: "2026-06-08",
        task_type: "sentence_challenge_generation",
        model: "test-model",
        call_count: 2,
        prompt_tokens: 18,
        completion_tokens: 5,
        total_tokens: 23,
        estimated_cost: 0.0015,
        failure_count: 1,
        daily_limit_hit_count: 1,
      },
    ],
  });
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  expect(await screen.findByRole("heading", { name: "Alpha 总览" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "邀请管理" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "账号管理" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "AI 使用量" })).toBeInTheDocument();
  expect(await screen.findByText("sentence_challenge_generation")).toBeInTheDocument();
  expect(screen.getByText("23")).toBeInTheDocument();
  expect(screen.getByText("0.0015")).toBeInTheDocument();
});

test("admin hides revoked invites by default and loads them when toggled", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  await screen.findByRole("button", { name: /家庭 01/ });
  expect(apiMocks.getAdminAlphaOverview).toHaveBeenLastCalledWith("secret", false);

  await userEvent.click(screen.getByRole("checkbox", { name: "显示已撤销邀请码" }));

  await waitFor(() =>
    expect(apiMocks.getAdminAlphaOverview).toHaveBeenLastCalledWith("secret", true),
  );
});

test("overview table renders invite family funnel and last activity", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  const row = await screen.findByRole("button", { name: /家庭 01/ });
  expect(row).toHaveTextContent("小星家长");
  expect(row).toHaveTextContent("summary_viewed");
  expect(row).toHaveTextContent("1 child");
  expect(row).toHaveTextContent("positive: 2");
  expect(row).toHaveTextContent("helpful");
  expect(row).toHaveTextContent("2026-05-29T10:00:00+08:00");
});

test("overview table renders minimal account fields", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  const row = await screen.findByRole("button", { name: /家庭 01/ });
  expect(row).toHaveTextContent("Account linked");
  expect(row).toHaveTextContent("pa***@example.com");
  expect(row).toHaveTextContent("Phone bound");
  expect(row).toHaveTextContent("2026-05-29T09:30:00+08:00");
  expect(row).not.toHaveTextContent("active sessions");
  expect(row).not.toHaveTextContent("migration conflicts");
});

test("overview table renders clear account fallbacks", async () => {
  apiMocks.getAdminAlphaOverview.mockResolvedValueOnce({
    families: [
      {
        ...overview.families[0],
        account_linked: false,
        account_email_masked: null,
        phone_bound: false,
        last_login_at: null,
      },
    ],
  });
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  const row = await screen.findByRole("button", { name: /家庭 01/ });
  expect(row).toHaveTextContent("No account");
  expect(row).toHaveTextContent("No email");
  expect(row).toHaveTextContent("Phone not bound");
  expect(row).toHaveTextContent("No last login");
});

test("clicking a family row renders simple timeline", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  await userEvent.click(await screen.findByRole("button", { name: /家庭 01/ }));

  expect(apiMocks.getAdminAlphaFamily).toHaveBeenCalledWith("secret", "parent-1");
  const timeline = await screen.findByLabelText("Family timeline");
  expect(within(timeline).getByText("alpha_parent_created")).toBeInTheDocument();
  expect(within(timeline).getByText("summary_viewed")).toBeInTheDocument();
  expect(within(timeline).getByText(/"summary_viewed": true/)).toBeInTheDocument();
  expect(screen.queryByText("小星同学")).not.toBeInTheDocument();
});

test("wrong token displays a clear error", async () => {
  apiMocks.getAdminAlphaOverview.mockRejectedValueOnce(new Error("Request failed: 403"));
  render(<AdminAlphaPage />);

  await userEvent.type(screen.getByLabelText("Admin token"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "进入" }));

  expect(
    await screen.findByRole("alert", { name: "Admin alpha error" }),
  ).toHaveTextContent("Token invalid or admin overview unavailable.");
  expect(screen.getByLabelText("Admin token")).toBeInTheDocument();
  expect(window.sessionStorage.getItem("wenlingo_alpha_admin_token")).toBeNull();
});

test("overview does not render writing text or AI feedback body", async () => {
  apiMocks.getAdminAlphaOverview.mockResolvedValueOnce({
    families: [
      {
        ...overview.families[0],
        invite_label: "家庭 Safe",
      },
    ],
  });
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  expect(await screen.findByText("家庭 Safe")).toBeInTheDocument();
  expect(screen.queryByText("孩子写作正文不能出现在管理端")).not.toBeInTheDocument();
  expect(screen.queryByText("AI feedback body should stay private")).not.toBeInTheDocument();
});

test("admin generates invites and shows one-time warning without browser storage", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");
  render(<AdminAlphaPage />);

  await screen.findByRole("button", { name: /家庭 01/ });
  await userEvent.clear(screen.getByLabelText("Invite count"));
  await userEvent.type(screen.getByLabelText("Invite count"), "1");
  await userEvent.clear(screen.getByLabelText("Label prefix"));
  await userEvent.type(screen.getByLabelText("Label prefix"), "Alpha QA");
  await userEvent.type(screen.getByLabelText("Issued note"), "June QA");
  await userEvent.click(screen.getByRole("button", { name: "生成邀请码" }));

  expect(apiMocks.createAdminAlphaInvites).toHaveBeenCalledWith("secret", {
    count: 1,
    label_prefix: "Alpha QA",
    issued_to_note: "June QA",
  });
  expect(await screen.findByText("ALPHA-NEWCODE")).toBeInTheDocument();
  expect(
    screen.getByText(
      "这些邀请码只显示一次。关闭页面后无法再次查看，请立即复制并安全保存。",
    ),
  ).toBeInTheDocument();
  expect(window.sessionStorage.getItem("wenlingo_alpha_admin_token")).toBe(
    "secret",
  );
  const sessionStorageContents = JSON.stringify({ ...window.sessionStorage });
  const localStorageContents = JSON.stringify({ ...window.localStorage });
  expect(sessionStorageContents).not.toContain("ALPHA-NEWCODE");
  expect(localStorageContents).not.toContain("ALPHA-NEWCODE");
});

test("admin renders account list and disables then enables account", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");
  render(<AdminAlphaPage />);

  expect(await screen.findAllByText("pa***@example.com")).not.toHaveLength(0);
  expect(screen.getByText("1 active session")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Disable account" }));
  expect(apiMocks.disableAdminAlphaAccount).toHaveBeenCalledWith(
    "secret",
    "account-1",
  );

  apiMocks.getAdminAlphaAccounts.mockResolvedValueOnce({
    accounts: [
      {
        account_id: "account-1",
        email_masked: "pa***@example.com",
        status: "disabled",
        parent_id: "parent-1",
        parent_display_name: "小星家长",
        children_count: 1,
        last_login_at: "2026-05-29T09:30:00+08:00",
        active_session_count: 0,
        created_at: "2026-05-28T09:30:00+08:00",
      },
    ],
  });
  await userEvent.click(await screen.findByRole("button", { name: "Enable account" }));
  expect(apiMocks.enableAdminAlphaAccount).toHaveBeenCalledWith(
    "secret",
    "account-1",
  );
});

test("admin revokes an issued invite and refreshes overview", async () => {
  apiMocks.getAdminAlphaOverview.mockResolvedValueOnce({
    families: [
      ...overview.families,
      {
        ...overview.families[0],
        invite_id: "invite-issued",
        invite_label: "Alpha QA 01",
        invite_status: "issued",
        parent_id: null,
        parent_display_name: null,
        child_count: 0,
        funnel_stage: "invited",
        assessment_completed_count: 0,
        summary_viewed: false,
        reaction_counts: {},
        latest_parent_feedback: null,
        last_event_at: null,
        account_linked: false,
        account_email_masked: null,
        phone_bound: false,
        last_login_at: null,
      },
    ],
  });
  apiMocks.getAdminAlphaOverview.mockResolvedValueOnce({
    families: [
      {
        ...overview.families[0],
        invite_id: "invite-issued",
        invite_label: "Alpha QA 01",
        invite_status: "revoked",
        parent_id: null,
        parent_display_name: null,
        child_count: 0,
        funnel_stage: "revoked",
        assessment_completed_count: 0,
        summary_viewed: false,
        reaction_counts: {},
        latest_parent_feedback: null,
        last_event_at: null,
        account_linked: false,
        account_email_masked: null,
        phone_bound: false,
        last_login_at: null,
      },
    ],
  });
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");

  render(<AdminAlphaPage />);

  expect(await screen.findByText("Alpha QA 01")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Revoke invite" }));

  expect(apiMocks.revokeAdminAlphaInvite).toHaveBeenCalledWith(
    "secret",
    "invite-issued",
  );
  await waitFor(() =>
    expect(apiMocks.getAdminAlphaOverview).toHaveBeenCalledTimes(2),
  );
  expect(await screen.findAllByText("revoked")).not.toHaveLength(0);
});

test("admin account action shows per-row pending state", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");
  let resolveDisable: (value: unknown) => void = () => undefined;
  apiMocks.disableAdminAlphaAccount.mockReturnValueOnce(
    new Promise((resolve) => {
      resolveDisable = resolve;
    }),
  );

  render(<AdminAlphaPage />);

  const button = await screen.findByRole("button", { name: "Disable account" });
  await userEvent.click(button);

  expect(screen.getByRole("button", { name: "Disabling..." })).toBeDisabled();

  resolveDisable({
    account: { account_id: "account-1", status: "disabled", revoked_session_count: 1 },
  });

  await waitFor(() =>
    expect(apiMocks.disableAdminAlphaAccount).toHaveBeenCalledWith("secret", "account-1"),
  );
});

test("admin account actions keep independent pending states", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");
  apiMocks.getAdminAlphaAccounts.mockResolvedValue({
    accounts: [
      {
        account_id: "account-1",
        email_masked: "pa***@example.com",
        status: "active",
        parent_id: "parent-1",
        parent_display_name: "小星家长",
        children_count: 1,
        last_login_at: "2026-05-29T09:30:00+08:00",
        active_session_count: 1,
        created_at: "2026-05-28T09:30:00+08:00",
      },
      {
        account_id: "account-2",
        email_masked: "qa***@example.com",
        status: "active",
        parent_id: "parent-2",
        parent_display_name: "QA 家长",
        children_count: 1,
        last_login_at: "2026-05-30T09:30:00+08:00",
        active_session_count: 1,
        created_at: "2026-05-28T09:30:00+08:00",
      },
    ],
  });
  let resolveFirstDisable: (value: unknown) => void = () => undefined;
  let resolveSecondDisable: (value: unknown) => void = () => undefined;
  apiMocks.disableAdminAlphaAccount.mockImplementation(
    (_token: string, accountId: string) =>
      new Promise((resolve) => {
        if (accountId === "account-1") {
          resolveFirstDisable = resolve;
          return;
        }
        resolveSecondDisable = resolve;
      }),
  );

  render(<AdminAlphaPage />);

  const buttons = await screen.findAllByRole("button", { name: "Disable account" });
  await userEvent.click(buttons[0]);
  await userEvent.click(buttons[1]);

  const pendingButtons = screen.getAllByRole("button", { name: "Disabling..." });
  expect(pendingButtons).toHaveLength(2);
  pendingButtons.forEach((pendingButton) => expect(pendingButton).toBeDisabled());

  resolveFirstDisable({
    account: { account_id: "account-1", status: "disabled", revoked_session_count: 1 },
  });

  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Enable account" })).toBeInTheDocument(),
  );
  expect(screen.getByRole("button", { name: "Disabling..." })).toBeDisabled();

  resolveSecondDisable({
    account: { account_id: "account-2", status: "disabled", revoked_session_count: 1 },
  });

  await waitFor(() =>
    expect(apiMocks.disableAdminAlphaAccount).toHaveBeenCalledWith("secret", "account-2"),
  );
});

test("admin deletes selected test accounts only after confirmation", async () => {
  window.sessionStorage.setItem("wenlingo_alpha_admin_token", "secret");
  render(<AdminAlphaPage />);

  await screen.findAllByText("pa***@example.com");
  await userEvent.click(screen.getByRole("checkbox", { name: /select pa\*\*\*@example\.com/i }));

  const deleteButton = screen.getByRole("button", { name: "Delete selected test accounts" });
  expect(deleteButton).toBeDisabled();

  await userEvent.type(screen.getByLabelText("Delete confirmation"), "DELETE TEST ACCOUNTS");
  expect(deleteButton).toBeEnabled();
  await userEvent.click(deleteButton);

  expect(apiMocks.deleteAdminAlphaTestAccounts).toHaveBeenCalledWith("secret", {
    account_ids: ["account-1"],
    confirm: "DELETE TEST ACCOUNTS",
  });
  expect(await screen.findByText("Deleted 1 test account.")).toBeInTheDocument();
});
