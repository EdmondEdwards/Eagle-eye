import type { ReactNode } from "react";
import {
  ChevronDownIcon,
  EagleEyeLogo,
  GlobeIcon,
  LayersIcon,
  SearchIcon
} from "./icons";

function HeaderSelect({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <button className="flex h-10 items-center gap-2 rounded-[6px] border border-white/10 bg-white/[0.03] px-3 text-[13px] text-[#d4e6f7] transition hover:border-[#58C7FF]/30 hover:bg-[#58C7FF]/[0.06]">
      <span className="text-[#8fb4d1]">{icon}</span>
      <span>{label}</span>
      <ChevronDownIcon className="h-3.5 w-3.5 text-[#8ca2b7]" />
    </button>
  );
}

export function TopHeader() {
  return (
    <header className="panel-surface flex h-[72px] items-center justify-between px-5">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-[6px] bg-[#58C7FF]/[0.12] p-2 text-[#86d8ff] shadow-[inset_0_0_18px_rgba(88,199,255,0.14)]">
            <EagleEyeLogo className="h-7 w-7" />
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[15px] font-semibold tracking-[0.18em] text-[#EAF4FF]">EAGLE EYE</span>
            <span className="hidden h-px w-28 bg-gradient-to-r from-[#58C7FF]/30 to-transparent xl:block" />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-[14px]">
        <div className="flex h-10 items-center gap-2 rounded-full border border-[#6EFF97]/20 bg-[#6EFF97]/[0.08] px-4 text-[12px] font-medium tracking-[0.18em] text-[#b8ffd0]">
          <span className="h-2.5 w-2.5 rounded-full bg-[#6EFF97] shadow-[0_0_10px_rgba(110,255,151,0.5)]" />
          <span>LIVE</span>
        </div>
        <div className="text-[13px] text-[#a7b8ca]">
          <span className="text-[#eaf4ff]">2024-06-15</span>
          <span className="ml-2 text-[#7f92a7]">14:32 UTC</span>
        </div>
        <HeaderSelect icon={<LayersIcon className="h-4 w-4" />} label="Layers" />
        <HeaderSelect icon={<GlobeIcon className="h-4 w-4" />} label="Map" />
      </div>

      <div className="flex items-center gap-[14px]">
        <label className="flex h-10 min-w-[220px] items-center gap-2 rounded-[6px] border border-white/10 bg-[#08111b]/85 px-3 text-[#93A8BD] shadow-[inset_0_0_18px_rgba(88,199,255,0.05)]">
          <SearchIcon className="h-4 w-4 text-[#7c93a7]" />
          <input
            className="w-full bg-transparent text-[13px] text-[#EAF4FF] outline-none placeholder:text-[#6c8094]"
            placeholder="Search..."
          />
        </label>
        <div className="h-11 w-11 overflow-hidden rounded-full border border-[#8db4d0]/30 bg-[radial-gradient(circle_at_30%_30%,#cf9567,#6d4b35_38%,#172435_80%)] shadow-[0_0_0_1px_rgba(255,255,255,0.04),inset_0_0_18px_rgba(255,255,255,0.08)]">
          <div className="h-full w-full bg-[radial-gradient(circle_at_50%_38%,rgba(255,255,255,0.18),transparent_32%),radial-gradient(circle_at_50%_105%,#233549_32%,transparent_33%)]" />
        </div>
      </div>
    </header>
  );
}
