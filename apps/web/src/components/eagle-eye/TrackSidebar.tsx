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

export function TrackSidebar() {
  return (
    <aside className="panel-surface h-full w-[300px] p-3">
      <div className="flex h-full flex-col gap-4">
        <section className="flex flex-col gap-3">
          <SectionTitle title="TRACKS" />
          <div className="flex flex-col gap-2">
            <TrackRow icon={<AircraftIcon className="h-full w-full" />} label="Aircraft" count="1,256" accent="#58C7FF" />
            <TrackRow icon={<ShipIcon className="h-full w-full" />} label="Maritime" count="342" accent="#6EFF97" />
            <TrackRow icon={<SatelliteIcon className="h-full w-full" />} label="Satellites" count="32" accent="#FFAA4D" />
            <TrackRow icon={<AlertIcon className="h-full w-full" />} label="Alerts" count="5" accent="#FF5C5C" />
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <SectionTitle title="FILTER" />
          <div className="flex flex-col gap-2">
            <FilterRow
              icon={<AircraftIcon className="h-4 w-4" />}
              value="AE1234"
              actionIcon={<CheckIcon className="h-3.5 w-3.5 text-[#6EFF97]" />}
              accent="#6EFF97"
            />
            <FilterRow
              icon={<CrosshairIcon className="h-4 w-4" />}
              value="543210987"
              actionIcon={<PlusIcon className="h-3.5 w-3.5" />}
              accent="#8fd4ff"
            />
            <FilterRow
              icon={<SatelliteIcon className="h-4 w-4" />}
              value="55012"
              actionIcon={<PlusIcon className="h-3.5 w-3.5" />}
              accent="#8fd4ff"
            />
          </div>
        </section>

        <div className="flex-1 rounded-[8px] border border-white/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.015),rgba(255,255,255,0.005))]" />
      </div>
    </aside>
  );
}
