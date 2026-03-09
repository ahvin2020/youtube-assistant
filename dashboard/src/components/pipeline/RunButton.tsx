"use client";

interface RunButtonProps {
  label: string;
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "primary" | "secondary";
}

export default function RunButton({
  label,
  onClick,
  loading = false,
  disabled = false,
  variant = "primary",
}: RunButtonProps) {
  const base = "inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer select-none disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-indigo-500 text-white hover:bg-indigo-600 disabled:hover:bg-indigo-500",
    secondary: "bg-slate-700 text-slate-200 border border-slate-600 hover:bg-slate-600 disabled:hover:bg-slate-700",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`${base} ${variants[variant]}`}
    >
      {loading && (
        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {label}
    </button>
  );
}
