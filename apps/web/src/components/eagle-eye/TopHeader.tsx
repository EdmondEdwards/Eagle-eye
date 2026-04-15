import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  ChevronDownIcon,
  EagleEyeLogo,
  GlobeIcon,
  LayersIcon,
  SearchIcon
} from "./icons";

type SelectOption = {
  label: string;
  onSelect: () => void;
};

function HeaderSelect({
  icon,
  label,
  options
}: {
  icon: ReactNode;
  label: string;
  options: SelectOption[];
}) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number; width: number } | null>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        setOpen(false);
      }
    }
    window.addEventListener("mousedown", handleClickOutside);
    return () => window.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!open) return;
    function updateMenuPosition() {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setMenuPosition({
        top: rect.bottom + 8,
        left: rect.left,
        width: Math.max(rect.width, 180)
      });
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex h-10 items-center gap-2 rounded-[6px] border border-white/10 bg-white/[0.03] px-3 text-[13px] text-[#d4e6f7] transition hover:border-[#58C7FF]/30 hover:bg-[#58C7FF]/[0.06]"
      >
        <span className="text-[#8fb4d1]">{icon}</span>
        <span>{label}</span>
        <ChevronDownIcon className="h-3.5 w-3.5 text-[#8ca2b7]" />
      </button>
      {open && menuPosition && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={menuRef}
              style={{ top: menuPosition.top, left: menuPosition.left, width: menuPosition.width }}
              className="fixed z-[80] rounded-[8px] border border-white/10 bg-[#0a1018]/96 p-1 shadow-[0_12px_30px_rgba(0,0,0,0.28)] backdrop-blur-xl"
            >
              {options.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => {
                    option.onSelect();
                    setOpen(false);
                  }}
                  className="flex w-full items-center rounded-[6px] px-3 py-2 text-left text-[13px] text-[#d5e7f7] transition hover:bg-white/[0.05]"
                >
                  {option.label}
                </button>
              ))}
            </div>,
            document.body
          )
        : null}
    </div>
  );
}

type TopHeaderProps = {
  statusLabel: string;
  statusTone: "live" | "replay" | "paused" | "offline" | "connecting";
  utcDisplay: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  layerLabel: string;
  mapLabel: string;
  layerOptions: SelectOption[];
  mapOptions: SelectOption[];
};

export function TopHeader({
  statusLabel,
  statusTone,
  utcDisplay,
  searchValue,
  onSearchChange,
  layerLabel,
  mapLabel,
  layerOptions,
  mapOptions
}: TopHeaderProps) {
  const statusClasses =
    statusTone === "live"
      ? "border-[#6EFF97]/20 bg-[#6EFF97]/[0.08] text-[#b8ffd0]"
      : statusTone === "paused"
        ? "border-[#FFAA4D]/20 bg-[#FFAA4D]/[0.08] text-[#ffd8ad]"
        : statusTone === "replay"
          ? "border-[#58C7FF]/20 bg-[#58C7FF]/[0.08] text-[#c9efff]"
          : statusTone === "offline"
            ? "border-[#ff8d8d]/20 bg-[#FF5C5C]/[0.08] text-[#ffd7d7]"
            : "border-white/12 bg-white/[0.05] text-[#d5e6f4]";
  const dotClasses =
    statusTone === "live"
      ? "bg-[#6EFF97] shadow-[0_0_10px_rgba(110,255,151,0.5)]"
      : statusTone === "paused"
        ? "bg-[#FFAA4D] shadow-[0_0_10px_rgba(255,170,77,0.35)]"
        : statusTone === "replay"
          ? "bg-[#58C7FF] shadow-[0_0_10px_rgba(88,199,255,0.35)]"
          : statusTone === "offline"
            ? "bg-[#FF5C5C]"
            : "bg-[#9db3c8]";

  return (
    <header className="panel-surface relative z-30 isolate flex h-[72px] items-center justify-between overflow-visible px-5">
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
        <div className={`flex h-10 items-center gap-2 rounded-full border px-4 text-[12px] font-medium tracking-[0.18em] ${statusClasses}`}>
          <span className={`h-2.5 w-2.5 rounded-full ${dotClasses}`} />
          <span>{statusLabel}</span>
        </div>
        <div className="text-[13px] text-[#a7b8ca]">{utcDisplay}</div>
        <HeaderSelect icon={<LayersIcon className="h-4 w-4" />} label={layerLabel} options={layerOptions} />
        <HeaderSelect icon={<GlobeIcon className="h-4 w-4" />} label={mapLabel} options={mapOptions} />
      </div>

      <div className="flex items-center gap-[14px]">
        <label className="flex h-10 min-w-[220px] items-center gap-2 rounded-[6px] border border-white/10 bg-[#08111b]/85 px-3 text-[#93A8BD] shadow-[inset_0_0_18px_rgba(88,199,255,0.05)]">
          <SearchIcon className="h-4 w-4 text-[#7c93a7]" />
          <input
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
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
