import settlementPayload from "@/public/data/settlement.json"

import type { LandingSite } from "@/lib/mars-landing"

export type IceBand = "shallow" | "buried" | "none" | "unknown"

export type WeatherBound = "this-pin" | "warm-bound"

export type SettlementBrief = {
  weatherBound: WeatherBound
  ice: IceBand
  stormNote: string
  digNote: string
  waterNote: string
  honesty: string
}

export const SETTLEMENT = settlementPayload

export const PACK_WEATHER_LAT = SETTLEMENT.site.lat
export const PACK_WEATHER_LON = SETTLEMENT.site.lon

const ICE_SHALLOW = 0.25
const ICE_BURIED = 0.4
const PACK_SITE_DEG = 1

export const isPackWeatherSite = (lat: number, lonEast: number) => {
  const dLat = lat - PACK_WEATHER_LAT
  const dLon = ((lonEast - PACK_WEATHER_LON + 540) % 360) - 180
  return Math.hypot(dLat, dLon) < PACK_SITE_DEG
}

export const iceBand = (site?: LandingSite): IceBand => {
  if (site?.ice_0_1m == null && site?.ice_1_5m == null) {
    return "unknown"
  }
  if (site.ice_0_1m != null && site.ice_0_1m >= ICE_SHALLOW) {
    return "shallow"
  }
  if (site.ice_1_5m != null && site.ice_1_5m >= ICE_BURIED) {
    return "buried"
  }
  return "none"
}

export const settlementBrief = (
  lat: number,
  lonEast: number,
  site?: LandingSite
): SettlementBrief => {
  const weatherBound: WeatherBound = isPackWeatherSite(lat, lonEast)
    ? "this-pin"
    : "warm-bound"
  const ice = iceBand(site)
  const { heating, solar, ml, terrain, eclss, dust } = SETTLEMENT
  const plain = terrain.regolith_plain
  const rock = terrain.rock_field

  const stormNote =
    weatherBound === "this-pin"
      ? `Detector trips sol ${ml.stormDetector.tripSol} from wind and temperature, no dust sensor. Optical depth ${dust.sol179} → ${dust.sol180}. Heat ${heating.clearMean} → ${heating.stormMean} kW. Solar ${solar.clearMean} → ${solar.stormMean} kWh/m².`
      : `Jezero-band series is a warm bound. Detector trips sol ${ml.stormDetector.tripSol}. Heat ${heating.clearMean} → ${heating.stormMean} kW. Solar ${solar.clearMean} → ${solar.stormMean} kWh/m².`

  const digNote = `Plain ${plain.energyWhPerM} Wh/m vs rock ${rock.energyWhPerM}. Stall ${plain.hazard} vs ${rock.hazard}. Planned haul ${ml.terrain.plannedWh.toLocaleString("en-US")} Wh vs naive ${ml.terrain.naiveWh.toLocaleString("en-US")}. Pack is ${ml.terrain.swarmPackWh.toLocaleString("en-US")} Wh.`

  let waterNote = `Makeup plus electrolysis is ${eclss.makeupPlusElectrolysisKgDay} kg/day for 100 people.`
  if (ice === "shallow") {
    waterNote = `Ice in the first metre. ${waterNote} That is why a first city leaves 18°N.`
  } else if (ice === "buried") {
    waterNote = `Ice below a metre. ${waterNote}`
  } else if (ice === "unknown") {
    waterNote = `SWIM does not score this latitude. Polar ice is certain; winter solar is not. ${waterNote}`
  } else if (weatherBound === "this-pin") {
    waterNote = `No shallow ice on this pin. ${waterNote} It has to be trucked or shipped.`
  } else {
    waterNote = `No shallow ice here. ${waterNote}`
  }

  return {
    weatherBound,
    ice,
    stormNote,
    digNote,
    waterNote,
    honesty:
      "Weather and ECLSS are simulated. The terrain grid is synthetic. Detector and cost models recovered the generator, not the planet.",
  }
}

export const sparklineLabel = () => {
  const { solar, storm } = SETTLEMENT
  return `Solar energy per sol over 730 sols. Clear sols average ${solar.clearMean} kilowatt-hours per square metre. Storm sols ${storm.startSol} to ${storm.endSol} drop to ${solar.stormMean}.`
}
