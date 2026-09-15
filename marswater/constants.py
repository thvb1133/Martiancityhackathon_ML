"""Physical constants for Mars and for closed-loop life support.

Values are given with their sources so that every number in the simulation can
be traced back to published figures rather than being tuned to taste.
"""

from __future__ import annotations

# --- Solar geometry -------------------------------------------------------
SOLAR_CONSTANT_1AU_W_M2 = 1361.0  # TSI at 1 AU (Kopp & Lean 2011)
MARS_SEMI_MAJOR_AXIS_AU = 1.523679
MARS_ECCENTRICITY = 0.0934
MARS_OBLIQUITY_DEG = 25.19
SOL_LENGTH_S = 88775.244  # mean solar day on Mars

# Mean top-of-atmosphere irradiance at Mars' semi-major axis.
MARS_MEAN_IRRADIANCE_W_M2 = SOLAR_CONSTANT_1AU_W_M2 / MARS_SEMI_MAJOR_AXIS_AU**2

# --- Atmosphere -----------------------------------------------------------
# Column dust optical depth. Clear northern-summer conditions sit near 0.3;
# regional storms reach 1-2; the 2018 global storm exceeded 5.
TAU_CLEAR = 0.35
TAU_REGIONAL_STORM = 1.5
TAU_GLOBAL_STORM = 4.5

# Fraction of extinguished beam radiation that still reaches the ground as
# diffuse skylight. Mars dust is strongly forward-scattering, so this is much
# higher than on Earth (Appelbaum & Flood 1990).
DIFFUSE_RECOVERY_FRACTION = 0.55

# --- Power hardware -------------------------------------------------------
PV_EFFICIENCY = 0.28  # triple-junction space cells, beginning of life
PV_DUST_SETTLING_DERATE = 0.88  # obscuration between cleaning events
PV_PACKING_FACTOR = 0.85  # cell area / deployed array area
BATTERY_ROUND_TRIP_EFFICIENCY = 0.90
KILOPOWER_UNIT_KWE = 10.0  # fission surface power unit, electrical output

# --- Per-crew-member life support demand ---------------------------------
# Consumption rates from the NASA Life Support Baseline Values and
# Assumptions Document (BVAD, NASA/TP-2015-218570).
O2_KG_PER_PERSON_SOL = 0.84
POTABLE_WATER_KG_PER_PERSON_SOL = 3.9  # drinking + food rehydration
HYGIENE_WATER_KG_PER_PERSON_SOL = 8.2  # washing, flush, laundry
FOOD_DRY_KG_PER_PERSON_SOL = 1.8

# Fraction of used water recovered by the ECLSS. ISS achieves ~0.93 today;
# the shortfall is what ISRU has to make up from the ground every sol.
WATER_LOOP_CLOSURE = 0.93

# --- Energy intensities ---------------------------------------------------
# Thermal mining of ice-cemented regolith: heat the deposit, capture vapour.
# Strongly deposit-dependent; 1.2 kWh/kg is mid-range for shallow ice.
ISRU_WATER_EXTRACTION_KWH_PER_KG = 1.2
# Water electrolysis, including compression of the product gases.
ELECTROLYSIS_KWH_PER_KG_O2 = 4.8
# Habitat thermal control, lighting, avionics and ISRU overhead per person.
HABITAT_OVERHEAD_KWE_PER_PERSON = 2.1
# Crop lighting for a closed greenhouse producing the full dry-food ration.
GREENHOUSE_KWH_PER_KG_FOOD = 27.0

# --- Propellant production ------------------------------------------------
# The dominant reason to site a Mars settlement on ice is not drinking water:
# a closed ECLSS recycles most of that. It is propellant. Returning a vehicle
# to Earth means making methane and oxygen on the surface via Sabatier
# (CO2 + 4 H2 -> CH4 + 2 H2O) with hydrogen from electrolysed ground water.
#
# For a ~1,200 t methalox load, roughly 1,175 t of water must be electrolysed;
# the Sabatier reaction returns about half of it, so net consumption is close
# to 600 t of mined water per departing vehicle.
PROPELLANT_WATER_KG_PER_LAUNCH = 600_000.0
PROPELLANT_PLANT_KWH_PER_KG_WATER = 5.3  # electrolysis, Sabatier, liquefaction
SYNOD_SOLS = 668.0  # Earth-Mars launch windows are ~26 months apart
DEFAULT_CREW_PER_RETURN_FLIGHT = 50.0

# --- Landed hardware mass -------------------------------------------------
# Mass is the real currency of a Mars campaign: every kilogram has to be flown
# from Earth, so "which site is better" ultimately means "which site needs
# fewer launches to support the same number of people".
PV_AREAL_MASS_KG_M2 = 2.0  # roll-out array including support structure
BATTERY_SPECIFIC_ENERGY_WH_KG = 180.0  # lithium-ion at pack level
FISSION_UNIT_MASS_KG = 1500.0  # Kilopower-class 10 kWe unit
EXCAVATOR_UNIT_THROUGHPUT_KG_PER_SOL = 15_000.0
EXCAVATOR_UNIT_MASS_KG = 1400.0
# The thermal extraction plant has to heat every kilogram of rock the
# excavators deliver, so its mass scales with sol throughput rather than with
# water output: heated augers, sealed chambers, condensers and spoil handling.
# 0.8 kg of plant per kg/sol of throughput is a plant that processes its own
# mass roughly every 1.25 sols.
PROCESSING_PLANT_MASS_KG_PER_KG_SOL = 0.8
STARSHIP_PAYLOAD_KG = 100_000.0  # advertised Mars-surface payload

# --- Site engineering limits ---------------------------------------------
MAX_LANDING_SLOPE_DEG = 15.0  # EDL and surface-mobility limit
MAX_ROCK_ABUNDANCE = 0.22  # areal fraction blocking array and habitat layout
# A mining fleet has to be maintained, fuelled and repaired by the crew, so it
# cannot grow without limit even if the mass could be landed.
MAX_EXCAVATOR_FLEET = 24
# Practical cleared-and-cabled solar farm footprint adjacent to a settlement.
MAX_PV_AREA_M2 = 1_500_000.0
