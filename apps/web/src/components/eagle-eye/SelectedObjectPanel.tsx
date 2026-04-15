import { ActionButtonRow } from "./ActionButtonRow";
import { MiniTrajectoryPreview } from "./MiniTrajectoryPreview";
import { StatRow } from "./StatRow";

export function SelectedObjectPanel() {
  return (
    <aside className="panel-surface h-full w-[320px] p-3">
      <div className="flex h-full flex-col gap-4">
        <section className="border-b border-white/8 pb-3">
          <div className="text-[12px] font-medium tracking-[0.18em] text-[#a8bed3]">SELECTED OBJECT</div>
          <div className="mt-4 text-[31px] font-semibold leading-none tracking-[0.01em] text-[#f3f8ff]">STARLINK-3215</div>
          <div className="mt-2 text-[14px] text-[#8093a6]">NORAD ID: 50321</div>
        </section>

        <section>
          <StatRow label="Status" value="ACTIVE" valueClassName="text-[#6EFF97]" />
          <StatRow label="Altitude" value="550 km" />
          <StatRow label="Speed" value="7.60 km/s" />
          <StatRow label="Orbit" value="LEO" valueClassName="text-[#58C7FF]" />
          <StatRow label="Pass Over" value="London, UK" aside="1m 5s.12" />
        </section>

        <section>
          <ActionButtonRow
            buttons={[
              { label: "Follow", primary: true },
              { label: "Trajectory" },
              { label: "More Info" }
            ]}
          />
        </section>

        <section className="border-y border-white/8 py-3">
          <MiniTrajectoryPreview />
        </section>

        <section className="flex-1">
          <StatRow label="Inclination" value="53.0°" />
          <StatRow label="Period" value="95.1 min" />
          <StatRow label="Next Pass" value="In 5m 12s" aside="14:37 UTC" />
        </section>
      </div>
    </aside>
  );
}
