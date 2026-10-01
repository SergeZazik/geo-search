"""Read an OSM file and turn the objects we care about into plain records.

Points of interest are nodes, open ways and areas (closed ways or multipolygon
relations) tagged with one of POI_KEYS. Administrative boundaries are areas
with boundary=administrative at the levels in ADMIN_LEVELS.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import osmium
from osmium.osm import Area, Node, TagList, Way

logger = logging.getLogger(__name__)

# Order matters: an object tagged both amenity=restaurant and tourism=hotel
# is stored as a restaurant.
POI_KEYS = ("amenity", "shop", "tourism", "leisure")

# Street furniture: plenty of objects, no use for place search.
SKIPPED_KINDS = {
    "amenity": frozenset(
        {
            "bench",
            "grit_bin",
            "hunting_stand",
            "parking_entrance",
            "parking_space",
            "vending_machine",
            "waste_basket",
            "waste_disposal",
        }
    ),
    "leisure": frozenset({"picnic_table"}),
}

# Ukraine: 4 = oblast (and Kyiv), 6 = raion, 8 = city, town or village.
ADMIN_LEVELS = frozenset({4, 6, 8})


@dataclass(frozen=True, slots=True)
class Names:
    name: str | None
    uk: str | None
    en: str | None
    ru: str | None

    @classmethod
    def from_tags(cls, tags: TagList) -> "Names":
        return cls(
            name=tags.get("name"),
            uk=tags.get("name:uk"),
            en=tags.get("name:en"),
            ru=tags.get("name:ru"),
        )


@dataclass(frozen=True, slots=True)
class PlaceRecord:
    osm_type: str
    osm_id: int
    category: str
    kind: str
    names: Names
    tags: dict[str, str]
    wkb: bytes


@dataclass(frozen=True, slots=True)
class AdminAreaRecord:
    osm_type: str
    osm_id: int
    admin_level: int
    names: Names
    wkb: bytes


type OsmRecord = PlaceRecord | AdminAreaRecord


def classify(tags: TagList) -> tuple[str, str] | None:
    """Return (category, kind) for a POI, e.g. ("amenity", "cafe"), or None."""
    for key in POI_KEYS:
        value = tags.get(key)
        if not value:
            continue
        # "cafe;restaurant" -> "cafe"
        kind = value.split(";", 1)[0].strip().lower()
        if kind and kind != "no" and kind not in SKIPPED_KINDS.get(key, ()):
            return key, kind
    return None


def admin_level(tags: TagList) -> int | None:
    if tags.get("boundary") != "administrative":
        return None
    try:
        level = int(tags.get("admin_level") or "")
    except ValueError:
        return None
    return level if level in ADMIN_LEVELS else None


class OsmReader:
    """Iterates over records in an .osm / .osm.pbf file.

    Objects whose geometry cannot be built (missing nodes at the edge of an
    extract, degenerate ways) are skipped and counted in `skipped`.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.skipped = 0
        self._wkb = osmium.geom.WKBFactory()

    def __iter__(self) -> Iterator[OsmRecord]:
        relevant = osmium.filter.KeyFilter(*POI_KEYS, "boundary")
        processor = osmium.FileProcessor(str(self.path)).with_areas(relevant).with_filter(relevant)
        for obj in processor:
            try:
                if isinstance(obj, Node):
                    yield from self._from_node(obj)
                elif isinstance(obj, Way):
                    yield from self._from_way(obj)
                elif isinstance(obj, Area):
                    yield from self._from_area(obj)
                # Relations arrive as areas once their member ways are assembled.
            except (osmium.InvalidLocationError, RuntimeError) as exc:
                self.skipped += 1
                logger.debug("Skipping %s%s: %s", obj.type_str(), obj.id, exc)

    def _from_node(self, node: Node) -> Iterator[OsmRecord]:
        poi = classify(node.tags)
        if poi:
            yield self._place("node", node.id, poi, node.tags, self._wkb.create_point(node))

    def _from_way(self, way: Way) -> Iterator[OsmRecord]:
        # Closed ways come back as areas, unless explicitly marked as lines.
        if way.is_closed() and way.tags.get("area") != "no":
            return
        poi = classify(way.tags)
        if poi:
            yield self._place("way", way.id, poi, way.tags, self._wkb.create_linestring(way))

    def _from_area(self, area: Area) -> Iterator[OsmRecord]:
        osm_type = "way" if area.from_way() else "relation"
        poi = classify(area.tags)
        level = admin_level(area.tags)
        if not poi and level is None:
            return
        wkb = self._wkb.create_multipolygon(area)
        if poi:
            yield self._place(osm_type, area.orig_id(), poi, area.tags, wkb)
        if level is not None:
            yield AdminAreaRecord(
                osm_type=osm_type,
                osm_id=area.orig_id(),
                admin_level=level,
                names=Names.from_tags(area.tags),
                wkb=bytes.fromhex(wkb),
            )

    @staticmethod
    def _place(
        osm_type: str, osm_id: int, poi: tuple[str, str], tags: TagList, wkb: str
    ) -> PlaceRecord:
        category, kind = poi
        return PlaceRecord(
            osm_type=osm_type,
            osm_id=osm_id,
            category=category,
            kind=kind,
            names=Names.from_tags(tags),
            tags={tag.k: tag.v for tag in tags},
            wkb=bytes.fromhex(wkb),
        )
