import type { ReactNode } from "react";

type FilterRowProps = {
  icon: ReactNode;
  value: string;
  actionIcon: ReactNode;
  accent: string;
  onClick?: () => void;
  onActionClick?: () => void;
};

export function FilterRow({ icon, value, actionIcon, accent, onClick, onActionClick }: FilterRowProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onClick?.();
      }}
      className="flex h-[56px] cursor-pointer items-center gap-3 rounded-[8px] border border-white/7 bg-white/[0.02] px-3 transition hover:border-white/12 hover:bg-white/[0.045]"
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-full text-sm" style={{ color: accent }}>
        {icon}
      </div>
      <span className="flex-1 text-[14px] text-[#dce9f5]">{value}</span>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onActionClick?.();
        }}
        className="flex h-7 w-7 items-center justify-center rounded-full border border-white/12 bg-white/[0.03] text-[#8da2b6] transition hover:border-[#58C7FF]/30 hover:text-[#c8e9ff]"
        aria-label={`Action for ${value}`}
      >
        {actionIcon}
      </button>
    </div>
  );
}
