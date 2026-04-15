import type { RefObject } from "react";

type GlobeViewportProps = {
  globeRef: RefObject<HTMLDivElement | null>;
  loading: boolean;
  statusText: string;
};

export function GlobeViewport({ globeRef, loading, statusText }: GlobeViewportProps) {
  return (
    <section className="panel-surface relative min-w-0 flex-1 overflow-hidden p-0">
      <div className="absolute inset-[18px] overflow-hidden rounded-[6px] border border-white/8">
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(3,8,16,0.4),rgba(2,6,13,0.4))]" />
        <div ref={globeRef} className="globe-host absolute inset-0" />
        <div className="pointer-events-none absolute inset-0 viewport-grid opacity-15" />
        {loading ? (
          <div className="absolute left-4 top-4 rounded-[6px] border border-white/10 bg-black/45 px-3 py-2 text-[12px] tracking-[0.14em] text-[#a9c1d6]">
            SYNCING VIEWPORT
          </div>
        ) : (
          <div className="absolute left-4 top-4 rounded-[6px] border border-white/10 bg-black/35 px-3 py-2 text-[12px] text-[#a9c1d6]">
            {statusText}
          </div>
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-[linear-gradient(180deg,transparent,rgba(2,6,13,0.38))]" />
        <div className="absolute bottom-4 right-4 rounded-[6px] border border-white/10 bg-black/45 px-2 py-1 text-[11px] tracking-[0.16em] text-[#8ea6bb]">
          CESIUM LIVE VIEW
        </div>
      </div>
    </section>
  );
}
