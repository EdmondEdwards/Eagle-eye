import type { EntityRecord, EventRecord, InvestigationBundle, SatelliteFovResponse } from "@eagle-eye/shared-types";
import { GlobeViewport } from "./GlobeViewport";
import { SelectedObjectPanel } from "./SelectedObjectPanel";
import { TimelinePanel } from "./TimelinePanel";
import { TopHeader } from "./TopHeader";
import { TrackSidebar } from "./TrackSidebar";

type EagleEyeLayoutProps = {
  setGlobeRef: (node: HTMLDivElement | null) => void;
  statusLabel: string;
  statusTone: "live" | "replay" | "paused" | "offline" | "connecting";
  utcDisplay: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  layerLabel: string;
  mapLabel: string;
  layerOptions: Array<{ label: string; onSelect: () => void }>;
  mapOptions: Array<{ label: string; onSelect: () => void }>;
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
  timelineEvents: EventRecord[];
  onTimelineEventClick: (event: EventRecord) => void;
  loading: boolean;
  statusText: string;
  passLabel: string;
  nextPassUtc: string;
};

export function EagleEyeLayout(props: EagleEyeLayoutProps) {
  return (
    <main className="eagle-eye-shell min-h-screen bg-[#060B12] p-4 text-[#EAF4FF]">
      <div className="mx-auto flex h-[calc(100vh-32px)] min-h-[900px] flex-col gap-3">
        <TopHeader
          statusLabel={props.statusLabel}
          statusTone={props.statusTone}
          utcDisplay={props.utcDisplay}
          searchValue={props.searchValue}
          onSearchChange={props.onSearchChange}
          layerLabel={props.layerLabel}
          mapLabel={props.mapLabel}
          layerOptions={props.layerOptions}
          mapOptions={props.mapOptions}
        />

        <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)_320px] gap-3">
          <TrackSidebar
            trackCounts={props.trackCounts}
            filterValues={props.filterValues}
            activeTrack={props.activeTrack}
            onTrackClick={props.onTrackClick}
            onFilterClick={props.onFilterClick}
            onFilterActionClick={props.onFilterActionClick}
          />
          <GlobeViewport setGlobeRef={props.setGlobeRef} loading={props.loading} statusText={props.statusText} />
          <SelectedObjectPanel
            selectedTitle={props.selectedTitle}
            selectedEntity={props.selectedEntity}
            selectedEvent={props.selectedEvent}
            bundle={props.bundle}
            satelliteFov={props.satelliteFov}
            followSelected={props.followSelected}
            onToggleFollow={props.onToggleFollow}
            onToggleTrajectory={props.onToggleTrajectory}
            onMoreInfo={props.onMoreInfo}
            trajectoryEnabled={props.trajectoryEnabled}
            showMoreInfo={props.showMoreInfo}
            passLabel={props.passLabel}
            nextPassUtc={props.nextPassUtc}
          />
        </div>

        <TimelinePanel timelineEvents={props.timelineEvents} onEventClick={props.onTimelineEventClick} />
      </div>
    </main>
  );
}
