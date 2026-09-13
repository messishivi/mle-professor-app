"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./theme-toggle";

const tabs = [
  { href: "/", label: "Pulse" },
  { href: "/saved", label: "Saved" },
  { href: "/consultant", label: "Consultant" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-20 h-14 border-b border-line-0 bg-bg-1">
      <div className="mx-auto flex h-full max-w-[1200px] items-center gap-8 px-6">
        <Link
          href="/"
          className="shrink-0 font-mono text-base font-semibold tracking-tight text-ink-0"
        >
          <span className="text-accent">▚</span> MLE Professor
        </Link>

        <nav
          aria-label="Sections"
          className="flex h-full items-center gap-1"
        >
          {tabs.map((t) => {
            const active =
              t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                aria-current={active ? "page" : undefined}
                className={`relative flex h-full shrink-0 items-center px-3 text-sm transition-colors duration-120 ${
                  active ? "text-ink-0" : "text-ink-1 hover:text-ink-0"
                }`}
              >
                {t.label}
                {active && (
                  <span
                    aria-hidden
                    className="absolute inset-x-3 -bottom-px h-0.5 rounded bg-accent"
                  />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto shrink-0">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
