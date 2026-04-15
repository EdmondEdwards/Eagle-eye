import { AircraftIcon, AlertIcon, CheckIcon, CrosshairIcon, FilterIcon, PlusIcon, SatelliteIcon, ShipIcon } from "./icons";
import { FilterRow } from "./FilterRow";
import { TrackRow } from "./TrackRow";

function SectionTitle({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-between border-b border-white/8 pb-3">
      <span className="text-[12px] font-medium tracking-[0.18em] text-[#a8bed3]">{title}</span>
      <FilterIcon className="h-4 w-4 text-[#5f7388]" />
    </div>
  );
}

type TrackSidebarProps = {
  trackCounts: {
    aircraft: number;
    maritime: number;
    satellites: number;
    alerts: number;
  };
  filterValues: string[];
  activeTrack: "aircraft" | "maritime" | "satellites" | "alerts" | null;
  onTrackClick: (track: "aircraft" | "maritime" | "satellites" | "alerts") => void;
  onFilterClick: (value: string) => void;
  onFilterActionClick: (value: string) => void;
};

export function TrackSidebar({ trackCounts, filterValues, activeTrack, onTrackClick, onFilterClick, onFilterActionClick }: TrackSidebarProps) {
  const resolvedFilters = filterValues.length ? filterValues : ["AE1234", "543210987", "55012"];

  return (
    <aside className="panel-surface h-full w-[300px] p-3">
      <div className="flex h-full flex-col gap-4">
        <section className="flex flex-col gap-3">
          <SectionTitle title="TRACKS" />
          <div className="flex flex-col gap-2">
            <TrackRow icon={<AircraftIcon className="h-full w-full" />} label="Aircraft" count={trackCounts.aircraft.toLocaleString()} accent="#58C7FF" active={activeTrack === "aircraft"} onClick={() => onTrackClick("aircraft")} />
            <TrackRow icon={<ShipIcon className="h-full w-full" />} label="Maritime" count={trackCounts.maritime.toLocaleString()} accent="#6EFF97" active={activeTrack === "maritime"} onClick={() => onTrackClick("maritime")} />
            <TrackRow icon={<SatelliteIcon className="h-full w-full" />} label="Satellites" count={trackCounts.satellites.toLocaleString()} accent="#FFAA4D" active={activeTrack === "satellites"} onClick={() => onTrackClick("satellites")} />
            <TrackRow icon={<AlertIcon className="h-full w-full" />} label="Alerts" count={trackCounts.alerts.toLocaleString()} accent="#FF5C5C" active={activeTrack === "alerts"} onClick={() => onTrackClick("alerts")} />
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <SectionTitle title="FILTER" />
          <div className="flex flex-col gap-2">
            {resolvedFilters.slice(0, 3).map((value, index) => (
              <FilterRow
                key={value}
                icon={
                  index === 0 ? (
                    <AircraftIcon className="h-4 w-4" />
                  ) : index === 1 ? (
                    <CrosshairIcon className="h-4 w-4" />
                  ) : (
                    <SatelliteIcon className="h-4 w-4" />
                  )
                }
                value={value}
                actionIcon={index === 0 ? <CheckIcon className="h-3.5 w-3.5 text-[#6EFF97]" /> : <PlusIcon className="h-3.5 w-3.5" />}
                accent={index === 0 ? "#6EFF97" : "#8fd4ff"}
                onClick={() => onFilterClick(value)}
                onActionClick={() => onFilterActionClick(value)}
              />
            ))}
          </div>
        </section>

        <div className="flex-1 rounded-[8px] border border-white/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.015),rgba(255,255,255,0.005))]" />
      </div>
    </aside>
  );
}
