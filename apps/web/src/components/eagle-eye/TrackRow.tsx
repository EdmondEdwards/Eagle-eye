import type { ReactNode } from "react";
import { ChevronRightIcon } from "./icons";

type TrackRowProps = {
  icon: ReactNode;
  label: string;
  count: string;
  accent: string;
};

export function TrackRow({ icon, label, count, accent }: TrackRowProps) {
  return (
    <button className="group flex h-16 w-full items-center gap-3 rounded-[8px] border border-white/7 bg-white/[0.02] px-3 transition hover:border-white/12 hover:bg-white/[0.045]">
      <div
        className="flex h-9 w-9 items-center justify-center rounded-[6px] border border-white/8 bg-black/20"
        style={{ color: accent, boxShadow: `inset 0 0 14px ${accent}22` }}
      >
        <div className="h-[18px] w-[18px]">{icon}</div>
      </div>
      <div className="min-w-0 flex-1 text-left">
        <div className="text-[14px] text-[#EAF4FF]">{label}</div>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[14px] text-[#d7e8f7]">{count}</span>
        <ChevronRightIcon className="h-4 w-4 text-[#7e93a6] transition group-hover:text-[#b8cfdf]" />
      </div>
    </button>
  );
}
