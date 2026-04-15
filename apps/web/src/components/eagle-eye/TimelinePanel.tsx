import type { EventRecord } from "@eagle-eye/shared-types";
import { DistressIcon, LaunchIcon, StormIcon } from "./icons";
import { TimelineEventRow } from "./TimelineEventRow";

type TimelinePanelProps = {
  timelineEvents: EventRecord[];
};

function eventMeta(event: EventRecord) {
  const title = event.title;
  const location =
    typeof event.properties?.location === "string"
      ? event.properties.location
      : typeof event.properties?.place === "string"
        ? event.properties.place
        : event.source;

  if (event.category.toLowerCase().includes("storm")) {
    return { icon: <StormIcon className="h-4 w-4" />, color: "#58C7FF", title, location };
  }
  if (event.category.toLowerCase().includes("launch") || event.title.toLowerCase().includes("launch")) {
    return { icon: <LaunchIcon className="h-4 w-4" />, color: "#FFAA4D", title, location };
  }
  return { icon: <DistressIcon className="h-4 w-4" />, color: "#FF7D4D", title, location };
}

export function TimelinePanel({ timelineEvents }: TimelinePanelProps) {
  return (
    <section className="panel-surface h-[190px] p-3">
      <div className="flex h-full flex-col gap-3">
        <div className="flex items-center gap-4 border-b border-white/8 pb-3">
          <span className="text-[12px] font-medium tracking-[0.18em] text-[#a8bed3]">TIMELINE</span>
          <div className="relative h-[26px] flex-1 overflow-hidden rounded-full border border-white/8 bg-[#07101a] px-6">
            <div className="absolute inset-x-6 top-1/2 h-px -translate-y-1/2 border-t border-dashed border-[#86a7c2]/30" />
            <div className="absolute left-[34%] top-[4px] h-[18px] w-[2px] rounded-full bg-[#FFAA4D] shadow-[0_0_10px_rgba(255,170,77,0.5)]" />
            <div className="absolute left-[34%] top-[22px] h-0 w-0 -translate-x-1/2 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-[#aab8c4]" />
            <div className="absolute inset-y-0 left-0 w-[42%] bg-[linear-gradient(90deg,transparent,rgba(88,199,255,0.28),transparent)] opacity-60" />
            <div className="absolute inset-0 flex items-center justify-center gap-3 text-[11px] tracking-[0.18em] text-[#EAF4FF]">
              <span className="text-[#73879b]">12:00</span>
              <span className="h-1.5 w-1.5 rounded-full bg-[#6EFF97]" />
              <span>LIVE</span>
              <span className="text-[#73879b]">18:00</span>
            </div>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-[185px_minmax(0,1fr)] gap-3">
          <div className="relative overflow-hidden rounded-[8px] border border-white/10 bg-[#07101a]">
            <div className="mini-preview-grid absolute inset-0 opacity-45" />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_40%,rgba(255,170,77,0.42),transparent_12%),radial-gradient(circle_at_78%_32%,rgba(88,199,255,0.3),transparent_18%),linear-gradient(180deg,rgba(12,20,30,0.7),rgba(5,10,16,0.95))]" />
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 185 110" fill="none" aria-hidden="true">
              <path d="M-8 62c34-16 68-20 101-10 20 6 55 8 96-10" stroke="rgba(255,255,255,0.34)" strokeWidth="1.2" />
              <path d="M2 50c24 6 39 6 54 0 16-7 30-7 41 0 20 12 48 14 86-4" stroke="rgba(88,199,255,0.46)" strokeWidth="1.1" />
            </svg>
          </div>

          <div className="overflow-hidden rounded-[8px] border border-white/8 bg-white/[0.015]">
            {timelineEvents.map((event) => {
              const meta = eventMeta(event);
              return (
                <TimelineEventRow
                  key={event.id}
                  icon={meta.icon}
                  color={meta.color}
                  time={new Intl.DateTimeFormat("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }).format(new Date(event.start_time))}
                  title={meta.title}
                  location={meta.location}
                />
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
