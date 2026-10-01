"""Prepare the OSM file for a region: download, filter by tags, cut the region out.

Every step writes its result to the data directory and is skipped next time
if the result is newer than its input, so `make import` after the first run
only spends time on loading.

    ukraine-latest.osm.pbf     downloaded from Geofabrik
    ukraine-filtered.osm.pbf   only POI tags and admin boundaries
    <region>.osm.pbf           bounding-box extract for the region
"""

import logging
import shutil
import subprocess
import urllib.request
from pathlib import Path

from etl.osm import POI_KEYS
from etl.regions import BBox, Region

logger = logging.getLogger(__name__)

# osmium tags-filter expressions; referenced nodes and ways are kept automatically.
TAG_FILTERS = (*(f"nwr/{key}" for key in POI_KEYS), "r/boundary=administrative")


def tags_filter_command(src: Path, dst: Path) -> list[str]:
    return ["osmium", "tags-filter", "--overwrite", "-o", str(dst), str(src), *TAG_FILTERS]


def extract_command(src: Path, dst: Path, bbox: BBox) -> list[str]:
    return [
        "osmium",
        "extract",
        "--overwrite",
        "--bbox",
        ",".join(str(c) for c in bbox),
        # Keep ways and boundary/multipolygon relations that cross the bbox whole,
        # so city limits and large parks are not cut at the edge.
        "--strategy",
        "smart",
        "--option",
        "types=multipolygon,boundary",
        "-o",
        str(dst),
        str(src),
    ]


def is_fresh(path: Path, source: Path) -> bool:
    return path.exists() and path.stat().st_mtime >= source.stat().st_mtime


def download(url: str, dst: Path) -> None:
    logger.info("Downloading %s", url)
    partial = dst.with_name(dst.name + ".part")
    with urllib.request.urlopen(url) as response, partial.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    partial.rename(dst)
    logger.info("Saved %s (%.0f MB)", dst, dst.stat().st_size / 1e6)


def run(command: list[str]) -> None:
    logger.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True)


def prepare_region(region: Region, data_dir: Path, source_url: str, *, refresh: bool) -> Path:
    """Return the path of an .osm.pbf with the region's data, building it if needed."""
    data_dir.mkdir(parents=True, exist_ok=True)
    dump = data_dir / "ukraine-latest.osm.pbf"
    filtered = data_dir / "ukraine-filtered.osm.pbf"

    if refresh or not dump.exists():
        download(source_url, dump)
    if not is_fresh(filtered, dump):
        run(tags_filter_command(dump, filtered))
    if region.bbox is None:
        return filtered

    extract = data_dir / f"{region.name}.osm.pbf"
    if not is_fresh(extract, filtered):
        run(extract_command(filtered, extract, region.bbox))
    return extract
