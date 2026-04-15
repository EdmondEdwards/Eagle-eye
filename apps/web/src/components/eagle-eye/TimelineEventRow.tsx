import type { ReactNode } from "react";

type TimelineEventRowProps = {
  icon: ReactNode;
  color: string;
  time: string;
  title: string;
  location: string;
};

export function TimelineEventRow({ icon, color, time, title, location }: TimelineEventRowProps) {
  return (
    <div className="flex items-center gap-3 border-b border-white/8 px-4 py-3 last:border-b-0">
      <div className="flex h-8 w-8 items-center justify-center rounded-full border border-white/8 bg-black/25" style={{ color }}>
        {icon}
      </div>
      <span className="w-12 text-[13px] text-[#9db1c4]">{time}</span>
      <div className="min-w-0 flex-1 text-[14px]">
        <span className="font-semibold text-[#edf6ff]">{title}</span>
        <span className="text-[#7e93a7]"> · {location}</span>
      </div>
    </div>
  );
}
