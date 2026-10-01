"""Command line interface for loading OpenStreetMap data.

python -m etl import --region dnipro   download, extract and load a region
python -m etl load path/to/file.osm.pbf  load an existing OSM file
python -m etl regions                    list known regions
"""

import argparse
import asyncio
import logging
import time
from pathlib import Path

from app.db import create_engine
from etl.loader import DEFAULT_BATCH_SIZE, LoadStats, load_records
from etl.osm import OsmReader
from etl.regions import DEFAULT_REGION, REGIONS, get_region
from etl.settings import EtlSettings
from etl.source import prepare_region

logger = logging.getLogger("etl")


async def load_file(
    path: Path, database_url: str, *, batch_size: int = DEFAULT_BATCH_SIZE
) -> LoadStats:
    engine = create_engine(database_url)
    reader = OsmReader(path)
    try:
        stats = await load_records(reader, engine, batch_size=batch_size)
    finally:
        await engine.dispose()
    if reader.skipped:
        logger.warning("Skipped %d objects with broken geometry", reader.skipped)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m etl", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    import_cmd = commands.add_parser("import", help="download, extract and load a region")
    import_cmd.add_argument("--region", default=DEFAULT_REGION, choices=sorted(REGIONS))
    import_cmd.add_argument(
        "--refresh", action="store_true", help="download a fresh dump even if one is cached"
    )
    import_cmd.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    load_cmd = commands.add_parser("load", help="load an existing .osm or .osm.pbf file")
    load_cmd.add_argument("path", type=Path)
    load_cmd.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    commands.add_parser("regions", help="list known regions")
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    settings = EtlSettings()

    if args.command == "regions":
        for region in REGIONS.values():
            print(region.name, region.bbox or "(whole dump)")
        return

    if args.command == "import":
        path = prepare_region(
            get_region(args.region),
            settings.data_dir,
            settings.osm_source_url,
            refresh=args.refresh,
        )
    else:
        path = args.path

    started = time.monotonic()
    asyncio.run(load_file(path, settings.database_url, batch_size=args.batch_size))
    logger.info("Loaded %s in %.1f s", path, time.monotonic() - started)
