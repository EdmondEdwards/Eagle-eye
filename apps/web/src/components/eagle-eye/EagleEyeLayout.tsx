import { GlobeViewport } from "./GlobeViewport";
import { SelectedObjectPanel } from "./SelectedObjectPanel";
import { TimelinePanel } from "./TimelinePanel";
import { TopHeader } from "./TopHeader";
import { TrackSidebar } from "./TrackSidebar";

export function EagleEyeLayout() {
  return (
    <main className="eagle-eye-shell min-h-screen bg-[#060B12] p-4 text-[#EAF4FF]">
      <div className="mx-auto flex h-[calc(100vh-32px)] min-h-[900px] flex-col gap-3">
        <TopHeader />

        <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)_320px] gap-3">
          <TrackSidebar />
          <GlobeViewport />
          <SelectedObjectPanel />
        </div>

        <TimelinePanel />
      </div>
    </main>
  );
}
