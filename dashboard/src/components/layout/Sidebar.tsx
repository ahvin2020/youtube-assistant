"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const MAIN_NAV = [
  { href: "/", label: "Home", icon: "🏠" },
  { href: "/projects", label: "Projects", icon: "📁" },
];

const OPERATIONS_NAV = [
  { href: "/hooks", label: "Hooks", icon: "🪝" },
  { href: "/topics", label: "Topics", icon: "💡" },
];

const SYSTEM_NAV = [
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

function NavSection({
  label,
  items,
  pathname,
}: {
  label: string;
  items: { href: string; label: string; icon: string }[];
  pathname: string;
}) {
  return (
    <div className="space-y-0.5">
      <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider hidden lg:block">
        {label}
      </div>
      {items.map((item) => {
        const isActive =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              isActive
                ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <span className="text-base">{item.icon}</span>
            <span className="hidden lg:block">{item.label}</span>
          </Link>
        );
      })}
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-16 lg:w-52 bg-slate-900/80 backdrop-blur-sm border-r border-slate-800 h-screen sticky top-0 shrink-0">
        {/* Logo */}
        <div className="p-3 lg:px-4 lg:py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-sm">
              🎬
            </div>
            <div className="hidden lg:block">
              <div className="text-sm font-bold text-slate-100 leading-tight">
                Mission Control
              </div>
              <div className="text-[10px] text-slate-500">
                YouTube Assistant
              </div>
            </div>
          </div>
        </div>

        {/* Nav sections */}
        <nav className="flex-1 p-2 space-y-4 overflow-y-auto">
          <NavSection label="Main" items={MAIN_NAV} pathname={pathname} />
          <NavSection label="Operations" items={OPERATIONS_NAV} pathname={pathname} />
          <NavSection label="System" items={SYSTEM_NAV} pathname={pathname} />
        </nav>

        {/* Status footer */}
        <div className="p-3 border-t border-slate-800 hidden lg:block">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>System online</span>
          </div>
        </div>
      </aside>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-sm border-t border-slate-800 z-50 flex">
        {[...MAIN_NAV, ...OPERATIONS_NAV, ...SYSTEM_NAV].map((item) => {
          const isActive =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex-1 flex flex-col items-center py-2 text-xs transition-colors ${
                isActive ? "text-indigo-300" : "text-slate-500"
              }`}
            >
              <span className="text-lg">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
