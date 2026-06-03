import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import AdminAlphaPage from "../src/app/admin/alpha/page";

const apiMocks = vi.hoisted(() => ({
  getAdminAlphaOverview: vi.fn(),
  getAdminAlphaFamily: vi.fn(),
}));

vi.mock("../src/lib/api", () => ({
  getAdminAlphaOverview: apiMocks.getAdminAlphaOverview,
  getAdminAlphaFamily: apiMocks.getAdminAlphaFamily,
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
    expect(apiMocks.getAdminAlphaOverview).toHaveBeenCalledWith("secret"),
  );
  expect(window.sessionStorage.getItem("wenlingo_alpha_admin_token")).toBe("secret");
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
