import type { RefObject } from "react";
import type { EntityRecord, EventRecord, InvestigationBundle, SatelliteFovResponse } from "@eagle-eye/shared-types";
import { GlobeViewport } from "./GlobeViewport";
import { SelectedObjectPanel } from "./SelectedObjectPanel";
import { TimelinePanel } from "./TimelinePanel";
import { TopHeader } from "./TopHeader";
import { TrackSidebar } from "./TrackSidebar";

type EagleEyeLayoutProps = {
  globeRef: RefObject<HTMLDivElement | null>;
  isLive: boolean;
  utcDisplay: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  trackCounts: {
    aircraft: number;
    maritime: number;
    satellites: number;
    alerts: number;
  };
  filterValues: string[];
  selectedTitle: string;
  selectedEntity: EntityRecord | null;
  selectedEvent: EventRecord | null;
  bundle: InvestigationBundle | null;
  satelliteFov: SatelliteFovResponse | null;
  followSelected: boolean;
  onToggleFollow: () => void;
  timelineEvents: EventRecord[];
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
          isLive={props.isLive}
          utcDisplay={props.utcDisplay}
          searchValue={props.searchValue}
          onSearchChange={props.onSearchChange}
        />

        <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)_320px] gap-3">
          <TrackSidebar trackCounts={props.trackCounts} filterValues={props.filterValues} />
          <GlobeViewport globeRef={props.globeRef} loading={props.loading} statusText={props.statusText} />
          <SelectedObjectPanel
            selectedTitle={props.selectedTitle}
            selectedEntity={props.selectedEntity}
            selectedEvent={props.selectedEvent}
            bundle={props.bundle}
            satelliteFov={props.satelliteFov}
            followSelected={props.followSelected}
            onToggleFollow={props.onToggleFollow}
            passLabel={props.passLabel}
            nextPassUtc={props.nextPassUtc}
          />
        </div>

        <TimelinePanel timelineEvents={props.timelineEvents} />
      </div>
    </main>
  );
}
