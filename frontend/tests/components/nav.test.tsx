import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Nav } from "@/components/nav";

const { mockPath } = vi.hoisted(() => ({ mockPath: { current: "/" } }));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPath.current,
}));

describe("Nav", () => {
  it("renders brand and all section tabs", () => {
    render(<Nav />);
    expect(
      screen.getByRole("link", { name: /MLE Professor/i }),
    ).toBeInTheDocument();
    for (const label of ["Pulse", "Papers", "Saved", "Consultant"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("marks the active tab with aria-current", () => {
    mockPath.current = "/saved";
    const { unmount } = render(<Nav />);
    expect(screen.getByRole("link", { name: "Saved" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Pulse" })).not.toHaveAttribute(
      "aria-current",
    );
    unmount();
  });

  it("treats / as the Pulse tab", () => {
    mockPath.current = "/";
    const { unmount } = render(<Nav />);
    expect(screen.getByRole("link", { name: "Pulse" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    unmount();
  });
});
