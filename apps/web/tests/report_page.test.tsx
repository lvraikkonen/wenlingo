import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ReportPageContent } from "../src/app/parent/[studentId]/report/page";

vi.mock("../src/components/FamilyTopbar", () => ({
  FamilyTopbar: ({ currentStudentId }: { currentStudentId: string }) => (
    <div data-testid="topbar">{currentStudentId}</div>
  ),
}));

const apiMocks = vi.hoisted(() => ({
  createReport: vi.fn(),
}));

vi.mock("../src/lib/api", () => ({
  createReport: apiMocks.createReport,
}));

test("report page renders a controlled state when report creation fails", async () => {
  apiMocks.createReport.mockRejectedValueOnce(new Error("Request failed: 404"));

  render(<ReportPageContent studentId="student-1" />);

  expect(screen.getByRole("heading", { name: "阶段报告" })).toBeInTheDocument();
  expect(
    await screen.findByText("阶段报告暂时无法生成，请稍后再试。"),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "回到当前孩子 Dashboard" })).toHaveAttribute(
    "href",
    "/children/student-1",
  );
  expect(screen.getByRole("link", { name: "返回孩子列表" })).toHaveAttribute(
    "href",
    "/parent/children",
  );
});
