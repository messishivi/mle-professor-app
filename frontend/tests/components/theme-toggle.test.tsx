import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { ThemeToggle } from "@/components/theme-toggle";

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  window.localStorage.clear();
});

describe("ThemeToggle", () => {
  it("toggles data-theme on <html> and persists the choice", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(
      screen.getByRole("button", { name: "Switch to light theme" }),
    );
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(window.localStorage.getItem("mle-theme")).toBe("light");

    await user.click(
      screen.getByRole("button", { name: "Switch to dark theme" }),
    );
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(window.localStorage.getItem("mle-theme")).toBe("dark");
  });

  it("syncs with a theme set before mount (by the head script)", async () => {
    document.documentElement.setAttribute("data-theme", "light");
    render(<ThemeToggle />);
    await screen.findByRole("button", { name: "Switch to dark theme" });
  });
});
