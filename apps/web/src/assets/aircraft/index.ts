import milAir from "./mil_air.png";
import cargoPlane from "./cargo_plane.png";
import commercialJet from "./commercial_jet.png";
import droneUav from "./drone_uav.png";
import helicopter from "./helicopter.png";
import turboprop from "./turboprop.png";

// Use only the provided raster references and alias the remaining categories onto them.
const awacs = cargoPlane;
const fighterJet = milAir;
const generalAviation = commercialJet;
const heavyJet = commercialJet;
const stealthFighter = milAir;

export const aircraftIcons = {
  commercial_jet: commercialJet,
  heavy_jet: heavyJet,
  cargo_plane: cargoPlane,
  turboprop,
  general_aviation: generalAviation,
  fighter_jet: fighterJet,
  stealth_fighter: stealthFighter,
  awacs,
  helicopter,
  drone_uav: droneUav
} as const;

export type AircraftIconName = keyof typeof aircraftIcons;

export const aircraftIconEntries = [
  { key: "commercial_jet", label: "Commercial Jet", src: commercialJet },
  { key: "heavy_jet", label: "Heavy Jet", src: heavyJet },
  { key: "cargo_plane", label: "Cargo Plane", src: cargoPlane },
  { key: "turboprop", label: "Turboprop", src: turboprop },
  { key: "general_aviation", label: "General Aviation", src: generalAviation },
  { key: "fighter_jet", label: "Fighter Jet", src: fighterJet },
  { key: "stealth_fighter", label: "Stealth Fighter", src: stealthFighter },
  { key: "awacs", label: "AWACS", src: awacs },
  { key: "helicopter", label: "Helicopter", src: helicopter },
  { key: "drone_uav", label: "Drone / UAV", src: droneUav }
] as const;

export {
  awacs,
  cargoPlane,
  commercialJet,
  droneUav,
  fighterJet,
  generalAviation,
  heavyJet,
  helicopter,
  milAir,
  stealthFighter,
  turboprop
};
