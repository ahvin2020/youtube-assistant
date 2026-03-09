"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const MAIN_NAV = [
  { href: "/", label: "Dashboard", icon: "\u{1F4CA}" },
];

const PIPELINE_NAV = [
  { href: "/idea", label: "Ideas", icon: "\u{1F4A1}" },
  { href: "/write", label: "Write", icon: "\u{270D}\u{FE0F}" },
  { href: "/thumbnail", label: "Thumbnail", icon: "\u{1F3A8}" },
  { href: "/cut", label: "Cut", icon: "\u{1F3AC}" },
  { href: "/enhance", label: "Enhance", icon: "\u{2728}" },
  { href: "/analyze", label: "Analyze", icon: "\u{1F4CA}" },
];

const DATA_NAV = [
  { href: "/hooks", label: "Hooks", icon: "\u{1FA9D}" },
];

const SYSTEM_NAV = [
  { href: "/settings", label: "Settings", icon: "\u{2699}\u{FE0F}" },
];

function NavSection({
  label,
  items,
  pathname,
  collapsed,
}: {
  label: string;
  items: { href: string; label: string; icon: string }[];
  pathname: string;
  collapsed: boolean;
}) {
  return (
    <div className="space-y-0.5">
      {!collapsed && (
        <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
          {label}
        </div>
      )}
      {items.map((item) => {
        const isActive =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            title={collapsed ? item.label : undefined}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
              isActive
                ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            } ${collapsed ? "justify-center" : ""}`}
          >
            <span className="text-base">{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </Link>
        );
      })}
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("sidebar-collapsed");
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar-collapsed", String(next));
  };

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={`hidden md:flex flex-col ${
          collapsed ? "w-16" : "w-52"
        } bg-slate-900/80 backdrop-blur-sm border-r border-slate-800 h-screen sticky top-0 shrink-0 transition-all duration-200`}
      >
        {/* Logo + collapse toggle */}
        <div className="p-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-sm shrink-0">
              {"\u{1F3AC}"}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-slate-100 leading-tight">
                  Mission Control
                </div>
                <div className="text-[10px] text-slate-500">
                  YouTube Assistant
                </div>
              </div>
            )}
            <button
              onClick={toggle}
              className="w-6 h-6 flex items-center justify-center rounded text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors shrink-0"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <svg
                className={`w-4 h-4 transition-transform duration-200 ${collapsed ? "rotate-180" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Nav sections */}
        <nav className="flex-1 p-2 space-y-4 overflow-y-auto">
          <NavSection label="Main" items={MAIN_NAV} pathname={pathname} collapsed={collapsed} />
          <NavSection label="Pipelines" items={PIPELINE_NAV} pathname={pathname} collapsed={collapsed} />
          <NavSection label="Data" items={DATA_NAV} pathname={pathname} collapsed={collapsed} />
          <NavSection label="System" items={SYSTEM_NAV} pathname={pathname} collapsed={collapsed} />
        </nav>

        {/* Status footer */}
        {!collapsed && (
          <div className="p-3 border-t border-slate-800">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>System online</span>
            </div>
          </div>
        )}
      </aside>

      {/* Mobile bottom tab bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-sm border-t border-slate-800 z-50 flex">
        {[...MAIN_NAV, ...PIPELINE_NAV.slice(0, 3), ...SYSTEM_NAV].map((item) => {
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
