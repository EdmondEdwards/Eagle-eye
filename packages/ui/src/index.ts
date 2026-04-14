export type LayerDefinition = {
  key: "aircraft" | "vessels" | "satellites" | "airspace" | "events" | "aois";
  label: string;
  color: string;
  disabled?: boolean;
};

export const layerDefinitions: readonly LayerDefinition[] = [
  { key: "aircraft", label: "Aircraft", color: "#ffd54a" },
  { key: "vessels", label: "Vessels", color: "#6ee7ff" },
  { key: "satellites", label: "Satellites", color: "#9af6b0" },
  { key: "airspace", label: "Airspace / TFR", color: "#ff9b3d" },
  { key: "events", label: "Events", color: "#ff6b6b" },
  { key: "aois", label: "AOIs", color: "#f8e16c" }
];

export const detailTabs = ["details", "events", "relationships", "notes"] as const;

export const theme = {
  background: "#09131c",
  panel: "#111d28",
  panelAlt: "#0e1721",
  border: "rgba(148, 163, 184, 0.16)",
  text: "#e6eef5",
  muted: "#8fa5b6",
  accent: "#ffd54a",
  accentSatellite: "#9af6b0",
  warning: "#ff9b3d",
  success: "#6ee7ff",
  critical: "#ff6b6b"
};
