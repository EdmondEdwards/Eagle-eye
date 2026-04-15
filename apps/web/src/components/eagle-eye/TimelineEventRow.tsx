import type { ReactNode } from "react";

type TimelineEventRowProps = {
  icon: ReactNode;
  color: string;
  time: string;
  title: string;
  location: string;
  onClick?: () => void;
};

export function TimelineEventRow({ icon, color, time, title, location, onClick }: TimelineEventRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-3 border-b border-white/8 px-4 py-3 text-left transition hover:bg-white/[0.04] last:border-b-0"
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-full border border-white/8 bg-black/25" style={{ color }}>
        {icon}
      </div>
      <span className="w-12 text-[13px] text-[#9db1c4]">{time}</span>
      <div className="min-w-0 flex-1 text-[14px]">
        <span className="font-semibold text-[#edf6ff]">{title}</span>
        <span className="text-[#7e93a7]"> · {location}</span>
      </div>
    </button>
  );
}
