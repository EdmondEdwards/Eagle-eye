export type LayerDefinition = {
  key: "aircraft" | "vessels" | "vesselPresence" | "satellites" | "airspace" | "webcams";
  label: string;
  color: string;
  disabled?: boolean;
};

export const layerDefinitions: readonly LayerDefinition[] = [
  { key: "aircraft", label: "Aircraft", color: "#ffd54a" },
  { key: "vessels", label: "Vessels", color: "#6ee7ff" },
  { key: "vesselPresence", label: "Vessel Presence", color: "#56c9ff" },
  { key: "satellites", label: "Satellites", color: "#9af6b0" },
  { key: "airspace", label: "Airspace / TFR", color: "#ff9b3d" },
  { key: "webcams", label: "Webcams", color: "#7a88a2", disabled: true }
];

export const detailTabs = ["details", "relationships", "timeline", "notes", "sources"] as const;

export const theme = {
  background: "#07111c",
  panel: "#101d2b",
  panelAlt: "#0b1522",
  border: "rgba(148, 163, 184, 0.18)",
  text: "#dbe7f4",
  muted: "#8aa0b6",
  accent: "#ffd54a",
  accentSatellite: "#9af6b0",
  warning: "#ff9b3d",
  success: "#6ee7ff"
};
