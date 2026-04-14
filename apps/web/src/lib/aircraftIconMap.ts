import type { Aircraft } from "@eagle-eye/shared-types";
import { aircraftIcons, type AircraftIconName } from "../assets/aircraft";

export type AircraftCategory =
  | "commercial_jet"
  | "heavy_jet"
  | "cargo_plane"
  | "turboprop"
  | "general_aviation"
  | "fighter_jet"
  | "stealth_fighter"
  | "awacs"
  | "helicopter"
  | "drone_uav";

const normalizedCategoryMap: Record<string, AircraftCategory> = {
  commercial: "commercial_jet",
  commercial_jet: "commercial_jet",
  airliner: "commercial_jet",
  heavy: "heavy_jet",
  heavy_jet: "heavy_jet",
  cargo: "cargo_plane",
  cargo_plane: "cargo_plane",
  transport: "cargo_plane",
  turboprop: "turboprop",
  prop: "general_aviation",
  ga: "general_aviation",
  general_aviation: "general_aviation",
  general: "general_aviation",
  fighter: "fighter_jet",
  fighter_jet: "fighter_jet",
  military: "fighter_jet",
  stealth: "stealth_fighter",
  stealth_fighter: "stealth_fighter",
  awacs: "awacs",
  aew: "awacs",
  helicopter: "helicopter",
  heli: "helicopter",
  drone: "drone_uav",
  uav: "drone_uav",
  drone_uav: "drone_uav"
};

const categoryRules: Array<{ category: AircraftCategory; patterns: RegExp[] }> = [
  { category: "awacs", patterns: [/\bawacs\b/i, /\baew\b/i, /\be-3\b/i, /\bsentry\b/i, /\bmainstay\b/i] },
  { category: "stealth_fighter", patterns: [/\bf-35\b/i, /\bf35\b/i, /\bf-22\b/i, /\bf22\b/i, /\bj-20\b/i, /\bsu-57\b/i, /\bb-2\b/i] },
  { category: "drone_uav", patterns: [/\buav\b/i, /\bdrone\b/i, /\bmq-?9\b/i, /\brq-?4\b/i, /\bpredator\b/i, /\breaper\b/i, /\bglobal hawk\b/i] },
  { category: "helicopter", patterns: [/\bhelicopter\b/i, /\bhelo\b/i, /\brotor\b/i] },
  { category: "cargo_plane", patterns: [/\bcargo\b/i, /\bfreight\b/i, /\bairlift\b/i, /\btransport\b/i, /\bc-17\b/i, /\bc-130\b/i, /\bil-76\b/i, /\ban-124\b/i] },
  { category: "turboprop", patterns: [/\batr\b/i, /\bdash[- ]?8\b/i, /\bq400\b/i, /\bturboprop\b/i, /\bking air\b/i, /\bcaravan\b/i] },
  { category: "general_aviation", patterns: [/\bcessna\b/i, /\bpiper\b/i, /\bcirrus\b/i, /\bbeech\b/i, /\bbonanza\b/i, /\bmooney\b/i] },
  { category: "heavy_jet", patterns: [/\ba380\b/i, /\b747\b/i, /\b777\b/i, /\b787\b/i, /\ba350\b/i, /\ba340\b/i, /\bil-96\b/i] }
];

const categoryColors: Record<AircraftCategory, string> = {
  commercial_jet: "#ffd54a",
  heavy_jet: "#ffe082",
  cargo_plane: "#ffb86b",
  turboprop: "#8ef7ff",
  general_aviation: "#d7f4ff",
  fighter_jet: "#ffd54a",
  stealth_fighter: "#b3c8ff",
  awacs: "#ffe8a0",
  helicopter: "#7affc6",
  drone_uav: "#b7ff8a"
};

export const aircraftCategoryIconMap: Record<AircraftCategory, AircraftIconName> = {
  commercial_jet: "commercial_jet",
  heavy_jet: "heavy_jet",
  cargo_plane: "cargo_plane",
  turboprop: "turboprop",
  general_aviation: "general_aviation",
  fighter_jet: "fighter_jet",
  stealth_fighter: "stealth_fighter",
  awacs: "awacs",
  helicopter: "helicopter",
  drone_uav: "drone_uav"
};

function normalizeCategory(input?: string | null): AircraftCategory | null {
  if (!input) return null;
  return normalizedCategoryMap[input.trim().toLowerCase().replace(/\s+/g, "_")] ?? null;
}

export function resolveAircraftCategory(aircraft: Aircraft): AircraftCategory {
  const explicit = normalizeCategory(aircraft.aircraft_category);
  if (explicit) return explicit;

  const haystack = [aircraft.operator, aircraft.callsign, aircraft.registration, aircraft.icao24].filter(Boolean).join(" ");
  for (const rule of categoryRules) {
    if (rule.patterns.some((pattern) => pattern.test(haystack))) {
      return rule.category;
    }
  }
  return "commercial_jet";
}

export function aircraftIconForCategory(category: AircraftCategory): string {
  return aircraftIcons[aircraftCategoryIconMap[category]];
}

export function aircraftIconForAircraft(aircraft: Aircraft): string {
  return aircraftIconForCategory(resolveAircraftCategory(aircraft));
}

export function aircraftColorForAircraft(aircraft: Aircraft): string {
  return categoryColors[resolveAircraftCategory(aircraft)];
}
