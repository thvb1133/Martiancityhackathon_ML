"""Headless demo: ``python -m marswater.cli``.

Prints the full argument in about twenty seconds -- model validation, the site
ranking, the population breakpoint, and the dust-storm case -- so the demo does
not depend on a browser, a projector resolution, or the venue WiFi.
"""

from __future__ import annotations

import argparse

import pandas as pd

from .pipeline import run_pipeline
from .simulate import (
    minimum_fission_units,
    SettlementConfig,
    dust_storm_resilience,
    mission_architecture_comparison,
    population_sweep,
    rank_sites,
)


def _rule(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="marswater",
        description="Water-driven site selection and resilience planning for Mars.",
    )
    parser.add_argument("--population", type=int, default=100,
                        help="target crew size for the primary ranking")
    parser.add_argument("--fission-units", type=int, default=4,
                        help="number of 10 kWe fission surface power units")
    parser.add_argument("--top", type=int, default=8,
                        help="how many ranked sites to print")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 50)

    config = SettlementConfig(fission_units=args.fission_units)

    print("MARSWATER -- Mars settlement water siting and resilience")
    print("=" * 56)
    print("training the water-yield model on the orbital survey ...")
    result = run_pipeline(random_state=args.seed, include_grid=False)

    _rule("1. Model validation (held-out cells, never trained on)")
    for line in result.report.summary_lines():
        print("  " + line)
    print("\n  permutation importance (drop in R2 when the feature is shuffled):")
    for name, value in result.report.feature_importance.items():
        bar = "#" * max(1, int(round(value * 40)))
        print(f"    {name:<26} {value:6.3f}  {bar}")

    _rule(f"2. Site ranking for a crew of {args.population}"
          " (by landed mass required)")
    ranked = rank_sites(result.named_sites, config, args.population)
    columns = [
        "rank", "name", "latitude_deg", "water_grade_wt_pct",
        "regolith_t_per_sol", "pv_area_km2", "power_mass_t", "water_mass_t",
        "landed_mass_t", "max_population", "feasible",
    ]
    print(ranked[columns].head(args.top).round(2).to_string(index=False))

    blocked = ranked[~ranked["feasible"]]
    if len(blocked):
        print(f"\n  {len(blocked)} site(s) not viable at this crew size:")
        for _, row in blocked.head(4).iterrows():
            print(f"    {row['name']}: {row['limiting_factor']}")

    _rule("3. Does the water prediction change the decision?")
    print(mission_architecture_comparison(
        result.named_sites, config, args.population).to_string(index=False))

    _rule("4. Where it breaks -- the shortlist as the city grows")
    sweep = population_sweep(result.named_sites, config)
    print(sweep.to_string(index=False))

    stalled = sweep[sweep["sites_viable"] == 0]
    if len(stalled):
        first_failure = int(stalled.iloc[0]["population"])
        best_site_row = result.named_sites[
            result.named_sites["name"] == ranked.iloc[0]["name"]
        ].iloc[0]
        needed = minimum_fission_units(best_site_row, first_failure, config)
        print(f"\n  At {first_failure} crew no shortlisted site works on "
              f"{config.fission_units} reactors.")
        if needed is None:
            print("    More power does not help: the limit is rock throughput, "
                  "so the fix is a larger mining fleet or a wetter deposit.")
        else:
            print(f"    {ranked.iloc[0]['name']} reopens at {needed} fission "
                  f"units ({needed * 10} kWe of surface power).")

    best = ranked.iloc[0]
    site_row = result.named_sites[
        result.named_sites["name"] == best["name"]
    ].iloc[0]

    _rule(f"5. Dust-storm resilience at the top site ({best['name']})")
    print(dust_storm_resilience(site_row, config, args.population)
          .to_string(index=False))

    _rule("6. Recommendation")
    print(f"  Land at : {best['name']}")
    print(f"  Position: {best['latitude_deg']:.1f} deg lat, "
          f"{best['longitude_deg']:.1f} deg lon, "
          f"{best['elevation_km']:.1f} km elevation")
    print(f"  Water   : {best['water_grade_wt_pct']:.1f} wt% "
          "(conservative lower bound of the model's prediction)")
    print(f"  Mining  : {best['isru_kwh_per_kg_water']:.1f} kWh per kg of water, "
          f"{best['regolith_t_per_sol']:.0f} t of regolith per sol")
    print(f"  Hardware: {best['landed_mass_t']:.0f} t landed "
          f"({best['launches']:.1f} Starship loads) for {args.population} crew")
    print(f"  Ceiling : {int(best['max_population'])} crew, then "
          f"{best['capacity_limit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
