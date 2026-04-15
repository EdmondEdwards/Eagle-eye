import type { EntityRecord, EventRecord, InvestigationBundle, SatelliteFovResponse } from "@eagle-eye/shared-types";
import { ActionButtonRow } from "./ActionButtonRow";
import { MiniTrajectoryPreview } from "./MiniTrajectoryPreview";
import { StatRow } from "./StatRow";

type SelectedObjectPanelProps = {
  selectedTitle: string;
  selectedEntity: EntityRecord | null;
  selectedEvent: EventRecord | null;
  bundle: InvestigationBundle | null;
  satelliteFov: SatelliteFovResponse | null;
  followSelected: boolean;
  onToggleFollow: () => void;
  onToggleTrajectory: () => void;
  onMoreInfo: () => void;
  trajectoryEnabled: boolean;
  showMoreInfo: boolean;
  passLabel: string;
  nextPassUtc: string;
};

function entityValue(entity: EntityRecord | null, key: string): string | null {
  const value = entity?.properties?.[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

export function SelectedObjectPanel({
  selectedTitle,
  selectedEntity,
  selectedEvent,
  bundle,
  satelliteFov,
  followSelected,
  onToggleFollow,
  onToggleTrajectory,
  onMoreInfo,
  trajectoryEnabled,
  showMoreInfo,
  passLabel,
  nextPassUtc
}: SelectedObjectPanelProps) {
  const noradId = entityValue(selectedEntity, "norad_cat_id") ?? entityValue(selectedEntity, "norad_id") ?? selectedEntity?.id ?? "--";
  const altitude =
    selectedEntity?.entity_kind === "satellite"
      ? `${entityValue(selectedEntity, "computed_alt_km") ?? entityValue(selectedEntity, "altitude_km") ?? entityValue(selectedEntity, "altitude_value") ?? "550"} km`
      : entityValue(selectedEntity, "altitude_m")
        ? `${(Number(entityValue(selectedEntity, "altitude_m")) / 1000).toFixed(0)} km`
        : "--";
  const speed =
    entityValue(selectedEntity, "computed_velocity_kms") ??
    entityValue(selectedEntity, "speed_kts") ??
    entityValue(selectedEntity, "velocity_kts") ??
    "--";
  const speedLabel = speed === "--" ? "--" : selectedEntity?.entity_kind === "satellite" ? `${Number(speed).toFixed(2)} km/s` : `${Math.round(Number(speed))} kts`;
  const passOver = bundle?.aoi_events?.[0]?.title ?? selectedEvent?.title ?? entityValue(selectedEntity, "operator") ?? "--";
  const inclination = entityValue(selectedEntity, "inclination_deg") ?? entityValue(selectedEntity, "inclination") ?? "--";
  const period = entityValue(selectedEntity, "period_min") ?? entityValue(selectedEntity, "orbit_period_min") ?? "--";

  return (
    <aside className="panel-surface h-full w-[320px] p-3">
      <div className="flex h-full flex-col gap-4">
        <section className="border-b border-white/8 pb-3">
          <div className="text-[12px] font-medium tracking-[0.18em] text-[#a8bed3]">SELECTED OBJECT</div>
          <div className="mt-4 text-[31px] font-semibold leading-none tracking-[0.01em] text-[#f3f8ff]">{selectedTitle}</div>
          <div className="mt-2 text-[14px] text-[#8093a6]">NORAD ID: {noradId}</div>
        </section>

        <section>
          <StatRow label="Status" value={selectedEntity || selectedEvent ? "ACTIVE" : "--"} valueClassName="text-[#6EFF97]" />
          <StatRow label="Altitude" value={altitude} />
          <StatRow label="Speed" value={speedLabel} />
          <StatRow label="Orbit" value={selectedEntity?.entity_kind === "satellite" ? "LEO" : (selectedEntity?.entity_kind?.toUpperCase() ?? "--")} valueClassName="text-[#58C7FF]" />
          <StatRow label="Pass Over" value={passOver} aside={nextPassUtc} />
        </section>

        <section>
          <ActionButtonRow
            buttons={[
              { label: followSelected ? "Following" : "Follow", primary: true, onClick: onToggleFollow },
              { label: trajectoryEnabled ? "Trajectory On" : "Trajectory", onClick: onToggleTrajectory },
              { label: showMoreInfo ? "Less Info" : "More Info", onClick: onMoreInfo }
            ]}
          />
        </section>

        <section className="border-y border-white/8 py-3">
          <MiniTrajectoryPreview />
        </section>

        <section className="flex-1">
          <StatRow label="Inclination" value={inclination === "--" ? "--" : `${inclination}°`} />
          <StatRow label="Period" value={period === "--" ? (satelliteFov ? `${satelliteFov.swath_km.toFixed(0)} km swath` : "--") : `${period} min`} />
          <StatRow label="Next Pass" value={passLabel} aside={nextPassUtc} />
          {showMoreInfo ? (
            <div className="mt-4 rounded-[8px] border border-white/8 bg-white/[0.02] p-3 text-[12px] text-[#96abbe]">
              <div className="mb-2 text-[11px] tracking-[0.18em] text-[#a8bed3]">DETAILS</div>
              <div>Entity Kind: {selectedEntity?.entity_kind ?? selectedEvent?.category ?? "--"}</div>
              <div className="mt-1">Observed: {selectedEntity?.observed_at ?? selectedEvent?.start_time ?? "--"}</div>
              <div className="mt-1">Related Events: {bundle?.events?.length ?? 0}</div>
              <div className="mt-1">Watchlists: {bundle?.watchlists?.length ?? 0}</div>
            </div>
          ) : null}
        </section>
      </div>
    </aside>
  );
}
