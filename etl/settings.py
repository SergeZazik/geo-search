from pathlib import Path

from app.config import Settings


class EtlSettings(Settings):
    osm_source_url: str = "https://download.geofabrik.de/europe/ukraine-latest.osm.pbf"
    data_dir: Path = Path("data")
