"""Bake a rust-coloured MOLA texture for the Cesium globe."""

from __future__ import annotations

import numpy as np
from PIL import Image

from mars_data import MOLA_16PPD, PROCESSED, ROOT, load_mola

PUBLIC_DATA = ROOT / "public" / "data"

# Elevation stops in metres, then sRGB. Rust / dust, not the blue MOLA rainbow.
_STOPS_M = np.array([-8000.0, -4000.0, -1500.0, 0.0, 2500.0, 7000.0, 14000.0, 21200.0])
_STOPS_RGB = np.array(
    [
        [42, 18, 16],
        [92, 36, 24],
        [154, 58, 32],
        [196, 90, 40],
        [212, 122, 66],
        [230, 176, 122],
        [240, 210, 168],
        [247, 234, 212],
    ],
    dtype=np.float64,
)


def wrap_lon_180(array: np.ndarray) -> np.ndarray:
    half = array.shape[1] // 2
    return np.concatenate((array[:, half:], array[:, :half]), axis=1)


def colorize(elev: np.ndarray) -> np.ndarray:
    t = np.interp(elev, _STOPS_M, np.arange(len(_STOPS_M)))
    lo = np.floor(t).astype(np.int32)
    hi = np.clip(lo + 1, 0, len(_STOPS_M) - 1)
    frac = (t - lo)[..., None]
    return _STOPS_RGB[lo] * (1.0 - frac) + _STOPS_RGB[hi] * frac


def hillshade(elev: np.ndarray) -> np.ndarray:
    dy, dx = np.gradient(elev.astype(np.float64))
    slope = np.pi / 2 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    azimuth = np.radians(315)
    altitude = np.radians(38)
    shaded = np.sin(altitude) * np.sin(slope) + np.cos(altitude) * np.cos(
        slope
    ) * np.cos(azimuth - aspect)
    return np.clip(shaded, 0.0, 1.0)


def handle_main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)

    elev = wrap_lon_180(load_mola(MOLA_16PPD))
    shade = hillshade(elev)
    rgb = colorize(elev)
    lit = rgb * (0.42 + 0.58 * shade[..., None])
    pixels = np.clip(lit, 0, 255).astype(np.uint8)
    image = Image.fromarray(pixels, mode="RGB")
    dest = PUBLIC_DATA / "mola_16ppd_mars.jpg"
    image.save(dest, format="JPEG", quality=88, optimize=True)
    print(f"wrote {dest} {dest.stat().st_size / 1e6:.1f} MB {image.size}")


if __name__ == "__main__":
    handle_main()
