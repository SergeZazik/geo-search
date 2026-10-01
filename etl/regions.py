from dataclasses import dataclass

type BBox = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


@dataclass(frozen=True, slots=True)
class Region:
    name: str
    # Area cut out of the Ukraine dump; None means the whole dump.
    bbox: BBox | None = None


# Bounding boxes cover the city limits with a small margin.
REGIONS = {
    region.name: region
    for region in (
        Region("ukraine"),
        Region("dnipro", (34.74, 48.32, 35.24, 48.60)),
        Region("kyiv", (30.23, 50.21, 30.83, 50.59)),
        Region("kharkiv", (36.10, 49.88, 36.46, 50.11)),
        Region("lviv", (23.90, 49.76, 24.13, 49.90)),
        Region("odesa", (30.60, 46.33, 30.83, 46.60)),
    )
}

DEFAULT_REGION = "dnipro"


def get_region(name: str) -> Region:
    try:
        return REGIONS[name.lower()]
    except KeyError:
        known = ", ".join(sorted(REGIONS))
        raise ValueError(f"Unknown region {name!r}. Known regions: {known}") from None
