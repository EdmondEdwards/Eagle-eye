import type { ReactNode } from "react";
import { AircraftIcon, SatelliteIcon, ShipIcon } from "./icons";

type Marker = {
  icon: ReactNode;
  top: string;
  left: string;
  color: string;
  rotate?: string;
};

const markers: Marker[] = [
  { icon: <AircraftIcon className="h-full w-full" />, top: "43%", left: "28%", color: "#58C7FF", rotate: "-8deg" },
  { icon: <AircraftIcon className="h-full w-full" />, top: "54%", left: "62%", color: "#58C7FF", rotate: "12deg" },
  { icon: <ShipIcon className="h-full w-full" />, top: "48%", left: "41%", color: "#6EFF97", rotate: "0deg" },
  { icon: <ShipIcon className="h-full w-full" />, top: "37%", left: "63%", color: "#6EFF97", rotate: "10deg" },
  { icon: <SatelliteIcon className="h-full w-full" />, top: "32%", left: "76%", color: "#FFAA4D", rotate: "18deg" },
  { icon: <SatelliteIcon className="h-full w-full" />, top: "67%", left: "18%", color: "#FFAA4D", rotate: "-12deg" }
];

export function GlobeViewport() {
  return (
    <section className="panel-surface relative min-w-0 flex-1 overflow-hidden p-0">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(110,170,215,0.09),transparent_44%),radial-gradient(circle_at_50%_0%,rgba(88,199,255,0.06),transparent_36%),linear-gradient(180deg,#030810,#040a12_38%,#02060d)]" />
      <div className="viewport-grid absolute inset-0 opacity-75" />
      <div className="star-layer absolute inset-0" />

      <div className="absolute inset-[18px] overflow-hidden rounded-[6px] border border-white/8">
        <div className="viewport-grid absolute inset-0 opacity-60" />
        <div className="star-layer absolute inset-0 opacity-70" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_46%,rgba(95,140,190,0.05),transparent_38%)]" />

        <div className="globe-shell absolute left-1/2 top-1/2 h-[86%] w-[72%] -translate-x-1/2 -translate-y-1/2">
          <div className="globe-atmosphere absolute inset-[5%] rounded-full" />
          <div className="globe-core absolute inset-[8%] overflow-hidden rounded-full">
            <div className="globe-ocean absolute inset-0" />
            <div className="globe-continent globe-continent-europe" />
            <div className="globe-continent globe-continent-africa" />
            <div className="globe-continent globe-continent-northamerica" />
            <div className="globe-continent globe-continent-southamerica" />
            <div className="globe-continent globe-continent-asia" />
            <div className="globe-city-lights absolute inset-0" />
            <div className="globe-latitude absolute inset-0" />
            <div className="globe-shading absolute inset-0" />
          </div>
        </div>

        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 680" fill="none" aria-hidden="true">
          <ellipse cx="500" cy="336" rx="320" ry="250" stroke="rgba(110,255,151,0.65)" strokeWidth="2" />
          <ellipse cx="520" cy="346" rx="420" ry="132" stroke="rgba(110,255,151,0.9)" strokeWidth="2" />
          <ellipse
            cx="500"
            cy="348"
            rx="398"
            ry="166"
            transform="rotate(-18 500 348)"
            stroke="rgba(255,170,77,0.95)"
            strokeWidth="2"
          />
          <ellipse
            cx="508"
            cy="346"
            rx="390"
            ry="110"
            transform="rotate(14 508 346)"
            stroke="rgba(88,199,255,0.7)"
            strokeWidth="1.7"
          />
          <ellipse
            cx="512"
            cy="342"
            rx="280"
            ry="198"
            transform="rotate(22 512 342)"
            stroke="rgba(110,255,151,0.8)"
            strokeWidth="1.7"
          />
          <circle cx="840" cy="220" r="7" fill="#d7ffe4" />
          <circle cx="840" cy="220" r="18" fill="rgba(110,255,151,0.18)" />
          <circle cx="168" cy="328" r="5" fill="#ffc384" />
          <circle cx="168" cy="328" r="16" fill="rgba(255,170,77,0.18)" />
          <circle cx="302" cy="168" r="6" fill="#baffcb" />
          <circle cx="302" cy="168" r="14" fill="rgba(110,255,151,0.16)" />
          <circle cx="860" cy="430" r="6" fill="#8dd9ff" />
          <circle cx="860" cy="430" r="16" fill="rgba(88,199,255,0.18)" />
        </svg>

        {markers.map((marker, index) => (
          <div
            key={`${marker.left}-${marker.top}-${index}`}
            className="absolute flex h-6 w-6 items-center justify-center"
            style={{ top: marker.top, left: marker.left, color: marker.color, transform: `rotate(${marker.rotate ?? "0deg"})` }}
          >
            {marker.icon}
          </div>
        ))}
      </div>
    </section>
  );
}
