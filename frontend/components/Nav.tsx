"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ViewerPicker } from "./ViewerPicker";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/digest", label: "My Digest" },
  { href: "/dashboard", label: "Manager Dashboard" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="border-b border-black/10 dark:border-white/15 sticky top-0 bg-background/90 backdrop-blur z-10">
      <div className="mx-auto max-w-5xl px-6 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
        <Link href="/" className="font-semibold tracking-tight">
          Git<span className="text-blue-600">Insight</span>
        </Link>
        <nav className="flex gap-4 text-sm">
          {LINKS.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`group relative py-0.5 transition-colors ${
                  active
                    ? "font-medium text-blue-600"
                    : "text-black/55 dark:text-white/55 hover:text-black dark:hover:text-white"
                }`}
              >
                {l.label}
                <span
                  className={`absolute -bottom-0.5 left-0 h-px bg-blue-600 transition-all duration-300 ease-out ${
                    active ? "w-full" : "w-0 group-hover:w-full"
                  }`}
                />
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto">
          <ViewerPicker />
        </div>
      </div>
    </header>
  );
}
