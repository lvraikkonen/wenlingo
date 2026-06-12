import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import ParentChildrenPage from "../src/app/parent/children/page";
import NewChildPage from "../src/app/parent/children/new/page";
import {
  createMyAlphaChild,
  getMyAlphaChildren,
  recordAlphaEvent,
} from "../src/lib/api";
import { ALPHA_PARENT_STORAGE_KEY } from "../src/lib/alphaParent";
import { ALPHA_SESSION_STORAGE_KEY } from "../src/lib/alphaSession";

const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
}));

vi.mock("../src/lib/api", () => ({
  getMyAlphaChildren: vi.fn(async () => ({
    parent: { id: "parent-1", display_name: "小星家长" },
    children: [
      {
        id: "student-1",
        name: "小星",
        grade_label: "四年级",
        persona: "real_child",
        level: 1,
        xp: 0,
        assessment_completed: false,
        dashboard_url: "/children/student-1",
        summary_url: "/parent/children/student-1/summary",
      },
    ],
  })),
  createMyAlphaChild: vi.fn(async () => ({
    child: {
      id: "student-2",
      nickname: "小月",
      name: "小月",
      grade_label: "五年级",
      persona: "real_child",
      level: 1,
      xp: 0,
    },
    dashboard_url: "/children/student-2",
    summary_url: "/parent/children/student-2/summary",
  })),
  isUnauthorizedError: (error: unknown) =>
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    error.status === 401,
  recordAlphaEvent: vi.fn(async () => undefined),
}));

beforeEach(() => {
  cleanup();
  window.localStorage.clear();
  push.mockClear();
  replace.mockClear();
  vi.mocked(getMyAlphaChildren).mockClear();
  vi.mocked(createMyAlphaChild).mockClear();
  vi.mocked(recordAlphaEvent).mockClear();
});

test("children list redirects to alpha start when session is unauthorized", async () => {
  vi.mocked(getMyAlphaChildren).mockRejectedValueOnce({ status: 401 });

  render(<ParentChildrenPage />);

  await waitFor(() => expect(replace).toHaveBeenCalledWith("/alpha/start"));
});

test("children list renders child card and parent actions", async () => {
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");

  render(<ParentChildrenPage />);

  expect(await screen.findByRole("heading", { name: "我的孩子" })).toBeInTheDocument();
  expect(getMyAlphaChildren).toHaveBeenCalledWith();
  expect(screen.getByText("小星")).toBeInTheDocument();
  expect(screen.getByText("四年级")).toBeInTheDocument();
  expect(screen.getByText("等待入门小试炼")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "创建孩子档案" })).toHaveAttribute(
    "href",
    "/parent/children/new",
  );
  expect(screen.getByRole("link", { name: "进入孩子空间" })).toHaveAttribute(
    "href",
    "/children/student-1",
  );
  expect(screen.getByRole("link", { name: "查看成长摘要" })).toHaveAttribute(
    "href",
    "/parent/children/student-1/summary",
  );
  expect(recordAlphaEvent).toHaveBeenCalledWith({
    event_type: "parent_children_viewed",
    parent_id: "parent-1",
    alpha_session_id: "session-1",
    payload: { path: "/parent/children", status: "viewed" },
  });
});

test("children list records child handoff click with student id", async () => {
  window.localStorage.setItem(ALPHA_SESSION_STORAGE_KEY, "session-1");

  render(<ParentChildrenPage />);

  const childLink = await screen.findByRole("link", { name: "进入孩子空间" });
  const clickEvent = new MouseEvent("click", {
    bubbles: true,
    cancelable: true,
  });
  clickEvent.preventDefault();
  childLink.dispatchEvent(clickEvent);

  expect(recordAlphaEvent).toHaveBeenCalledWith({
    event_type: "child_handoff_clicked",
    parent_id: "parent-1",
    student_id: "student-1",
    alpha_session_id: "session-1",
    payload: { path: "/parent/children", status: "clicked" },
  });
});

test("children page logs out only the current browser and clears local alpha family marker", async () => {
  window.localStorage.setItem(ALPHA_PARENT_STORAGE_KEY, "parent-1");
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = input.toString();
    if (url.endsWith("/api/auth/logout")) {
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<ParentChildrenPage />);

  fireEvent.click(await screen.findByRole("button", { name: "退出当前浏览器登录" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/auth/logout",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
  });
  expect(window.localStorage.getItem(ALPHA_PARENT_STORAGE_KEY)).toBeNull();
  expect(replace).toHaveBeenCalledWith("/alpha/start");
});

test("new child page validates required nickname before submit", async () => {
  render(<NewChildPage />);
  fireEvent.change(screen.getByLabelText("孩子怎么称呼？"), {
    target: { value: "   " },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建孩子档案" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("请填写孩子昵称。");
  expect(createMyAlphaChild).not.toHaveBeenCalled();
});

test("new child page rejects nickname longer than 24 before submit", async () => {
  render(<NewChildPage />);
  fireEvent.change(screen.getByLabelText("孩子怎么称呼？"), {
    target: { value: "一二三四五六七八九十一二三四五六七八九十一二三四五" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建孩子档案" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("孩子昵称最多 24 个字。");
  expect(createMyAlphaChild).not.toHaveBeenCalled();
});

test("new child page rejects invalid grade before submit", async () => {
  render(<NewChildPage />);
  fireEvent.change(screen.getByLabelText("孩子怎么称呼？"), {
    target: { value: "小月" },
  });
  fireEvent.change(screen.getByLabelText("孩子现在几年级？"), {
    target: { value: "" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建孩子档案" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("请选择 3-6 年级。");
  expect(createMyAlphaChild).not.toHaveBeenCalled();
});

test("new child page creates child and shows handoff confirmation", async () => {
  render(<NewChildPage />);
  fireEvent.change(screen.getByLabelText("孩子怎么称呼？"), {
    target: { value: "小月" },
  });
  fireEvent.change(screen.getByLabelText("孩子现在几年级？"), {
    target: { value: "5" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建孩子档案" }));

  await waitFor(() => {
    expect(createMyAlphaChild).toHaveBeenCalledWith({
      nickname: "小月",
      grade: 5,
    });
  });
  expect(screen.getByRole("heading", { name: "小月已加入小文星球！" })).toBeInTheDocument();
  expect(screen.getByText("现在可以把设备交给小月，开始第一次语文冒险。")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "进入小文星球" })).toHaveAttribute(
    "href",
    "/children/student-2",
  );
});
