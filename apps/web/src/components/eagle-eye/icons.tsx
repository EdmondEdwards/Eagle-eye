import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function iconDefaults(props: IconProps) {
  return {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props
  };
}

export function EagleEyeLogo(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="M2.5 12.3 12 4l9.5 3.7L12 20z" fill="currentColor" opacity="0.2" stroke="none" />
      <path d="M2.5 12.3 12 4l9.5 3.7L12 20z" />
      <path d="m6 11 6 2.2L18 8.5" />
      <path d="m7.2 13.4 4.8 1.7 3.2-2" />
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

export function AircraftIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="m11.8 2.5 1.9 6.2 5.4 2-1 1.6-4.7-.8 2.2 7.1-1.6.7-3.7-6-3.9 1-.9 3.1H3.8l.9-4.2 3.7-1.6-.5-5.8 1.9-.6 2 5.2 1.5-.6-1.3-5.8z" />
    </svg>
  );
}

export function ShipIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="M4 14.5 12 7l8 7.5" />
      <path d="M7 12.4h10v4.1L12 19l-5-2.5z" />
      <path d="M3.2 18.5c1 .8 2.1 1.2 3.3 1.2s2.3-.4 3.3-1.2c1 .8 2.1 1.2 3.3 1.2s2.3-.4 3.3-1.2c1 .8 2.1 1.2 3.3 1.2" />
    </svg>
  );
}

export function SatelliteIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <rect x="9" y="9" width="6" height="6" rx="1.2" />
      <path d="m15 10 4-3" />
      <path d="m9 14-4 3" />
      <path d="M5.5 5.5 9 9" />
      <path d="M15 15 18.5 18.5" />
      <path d="M3 5.5h4v4H3z" />
      <path d="M17 14.5h4v4h-4z" />
    </svg>
  );
}

export function AlertIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="M12 4 21 20H3z" />
      <path d="M12 9v4.5" />
      <circle cx="12" cy="17" r=".8" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function FilterIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="M4 6h16" />
      <path d="M7 12h10" />
      <path d="M10 18h4" />
    </svg>
  );
}

export function CrosshairIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <circle cx="12" cy="12" r="5" />
      <path d="M12 2.5v3" />
      <path d="M12 18.5v3" />
      <path d="M2.5 12h3" />
      <path d="M18.5 12h3" />
    </svg>
  );
}

export function GlobeIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <circle cx="12" cy="12" r="8" />
      <path d="M4 12h16" />
      <path d="M12 4a12.4 12.4 0 0 1 0 16" />
      <path d="M12 4a12.4 12.4 0 0 0 0 16" />
    </svg>
  );
}

export function LayersIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="m12 4 8 4-8 4-8-4 8-4Z" />
      <path d="m4 12 8 4 8-4" />
      <path d="m4 16 8 4 8-4" />
    </svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="m5 12 4.2 4.2L19 6.5" />
    </svg>
  );
}

export function LaunchIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="m9 14 6-6" />
      <path d="M8 10.5c0-2.5 1.7-4.2 4.2-4.2l1.3 1.3c0 2.5-1.7 4.2-4.2 4.2L8 10.5Z" />
      <path d="m6.2 13.8-1.8 4.2 4.2-1.8" />
      <path d="M14 6h4v4" />
    </svg>
  );
}

export function StormIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="M5.5 14.5a4.5 4.5 0 1 1 1.1-8.9A5 5 0 0 1 17 8.1a3.7 3.7 0 1 1 1 7.4z" />
      <path d="m11 13-2 4h3l-1 4 4-6h-3l2-4z" />
    </svg>
  );
}

export function DistressIcon(props: IconProps) {
  return (
    <svg {...iconDefaults(props)}>
      <path d="M4 18h16" />
      <path d="m12 4 3 7H9z" />
      <path d="M8 18v-2.5a4 4 0 1 1 8 0V18" />
    </svg>
  );
}
