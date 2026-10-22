import os
from pathlib import Path

import pytest

from etl.osm import STREET_HIGHWAYS
from etl.regions import get_region
from etl.source import (
    FILTERS_STAMP,
    extract_command,
    is_fresh,
    prepare_region,
    tags_filter_command,
)

CACHED_FILES = ("ukraine-latest.osm.pbf", "ukraine-filtered.osm.pbf", "dnipro.osm.pbf")


def test_tags_filter_keeps_poi_keys_admin_boundaries_and_settlements() -> None:
    command = tags_filter_command(Path("in.pbf"), Path("out.pbf"))
    assert command[:2] == ["osmium", "tags-filter"]
    assert {"nwr/amenity", "nwr/shop", "nwr/tourism", "nwr/leisure"} <= set(command)
    assert "r/boundary=administrative" in command
    # Closed ways and multipolygons; place nodes have no outline.
    assert "wr/place=city,town,village" in command


def test_tags_filter_keeps_street_types_only() -> None:
    command = tags_filter_command(Path("in.pbf"), Path("out.pbf"))
    [streets] = [arg for arg in command if arg.startswith("w/highway=")]
    highways = set(streets.removeprefix("w/highway=").split(","))
    assert highways == set(STREET_HIGHWAYS)
    assert {"residential", "pedestrian"} <= highways
    assert not highways & {"primary_link", "footway", "path", "service", "track"}


def test_extract_uses_bbox_and_keeps_relations_whole() -> None:
    command = extract_command(Path("in.pbf"), Path("out.pbf"), (34.7, 48.3, 35.2, 48.6))
    assert command[command.index("--bbox") + 1] == "34.7,48.3,35.2,48.6"
    assert command[command.index("--strategy") + 1] == "smart"


def test_unknown_region_lists_known_ones() -> None:
    with pytest.raises(ValueError, match="dnipro"):
        get_region("atlantis")


def test_is_fresh_compares_modification_times(tmp_path: Path) -> None:
    source, result = tmp_path / "source", tmp_path / "result"
    source.touch()
    assert not is_fresh(result, source)
    result.touch()
    os.utime(source, (0, 0))
    assert is_fresh(result, source)
    os.utime(source, (result.stat().st_mtime + 10,) * 2)
    assert not is_fresh(result, source)


def test_prepare_region_reuses_cached_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in CACHED_FILES:
        (tmp_path / name).touch()
    (tmp_path / "ukraine-filtered.filters").write_text(FILTERS_STAMP)
    calls: list[str] = []
    monkeypatch.setattr("etl.source.download", lambda *args: calls.append("download"))
    monkeypatch.setattr("etl.source.run", lambda command: calls.append(command[1]))

    path = prepare_region(get_region("dnipro"), tmp_path, "http://example", refresh=False)

    assert path == tmp_path / "dnipro.osm.pbf"
    assert calls == []


@pytest.mark.parametrize("stamp", [None, "nwr/amenity\n"], ids=["no stamp", "other filters"])
def test_prepare_region_refilters_when_filters_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stamp: str | None
) -> None:
    # Files from an earlier import, each newer than its input.
    for mtime, name in enumerate(CACHED_FILES, start=1):
        path = tmp_path / name
        path.touch()
        os.utime(path, (mtime, mtime))
    stamp_path = tmp_path / "ukraine-filtered.filters"
    if stamp is not None:
        stamp_path.write_text(stamp)
    calls: list[str] = []

    def fake_run(command: list[str]) -> None:
        calls.append(command[1])
        Path(command[command.index("-o") + 1]).touch()

    monkeypatch.setattr("etl.source.run", fake_run)

    prepare_region(get_region("dnipro"), tmp_path, "http://example", refresh=False)

    assert calls == ["tags-filter", "extract"]
    assert stamp_path.read_text() == FILTERS_STAMP


def test_prepare_whole_country_skips_extract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_download(url: str, dst: Path) -> None:
        calls.append("download")
        dst.touch()

    def fake_run(command: list[str]) -> None:
        calls.append(command[1])
        Path(command[command.index("-o") + 1]).touch()

    monkeypatch.setattr("etl.source.download", fake_download)
    monkeypatch.setattr("etl.source.run", fake_run)

    path = prepare_region(get_region("ukraine"), tmp_path, "http://example", refresh=False)

    assert path == tmp_path / "ukraine-filtered.osm.pbf"
    assert calls == ["download", "tags-filter"]
    assert (tmp_path / "ukraine-filtered.filters").read_text() == FILTERS_STAMP
