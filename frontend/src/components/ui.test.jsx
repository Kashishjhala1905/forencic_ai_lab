import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RiskBadge, StatusPill } from "./ui";

describe("accessible status indicators", () => {
  it("risk badge always carries a text label, not just colour", () => {
    for (const [k, t] of [["LOW", "LOW RISK"], ["HIGH", "HIGH RISK"], ["INSUFFICIENT", /INSUFFICIENT EVIDENCE/]]) {
      const { unmount } = render(<RiskBadge category={k} />); expect(screen.getByText(t)).toBeInTheDocument(); unmount();
    }
  });
  it("status pill shows words", () => { render(<StatusPill status="fail" />); expect(screen.getByText("Fail")).toBeInTheDocument(); });
  it("renders a dash when there is no category", () => { render(<RiskBadge category={null} />); expect(screen.getByText("—")).toBeInTheDocument(); });
});
