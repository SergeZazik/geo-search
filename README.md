# geo-search

Search places on the map of Ukraine. The service loads OpenStreetMap data into
PostGIS and serves it as GeoJSON: places inside a bounding box, or places within
a radius, nearest first.

Next up: plain-language search (`POST /search`, e.g. *"cafes within 500 m of the
embankment in Dnipro"*). An LLM turns the query into a typed filter and the
service builds the spatial query. See [Roadmap](#roadmap).

**Stack:** Python 3.12, FastAPI (async), Pydantic v2, SQLAlchemy 2 + GeoAlchemy2,
asyncpg, Alembic, PostgreSQL 16 + PostGIS, pyosmium / osmium-tool, Docker,
pytest + testcontainers.

## Quick start

```bash
cp .env.example .env     # optional: defaults work out of the box
make up                  # PostGIS + migrations + API on http://localhost:8000
make import              # load Dnipro (default region)
```

`make import` downloads the Ukraine extract from Geofabrik once, keeps
only the tags the service uses, cuts out the region with `osmium extract` and
loads it. Later runs reuse the cached files.

```bash
make import REGION=kyiv      # dnipro, kyiv, kharkiv, lviv, odesa
make import REGION=ukraine   # the whole country, takes tens of minutes
```

Interactive API docs: http://localhost:8000/docs

## API

### `GET /places`: places in a bounding box

```bash
curl 'localhost:8000/places?bbox=35.02,48.45,35.07,48.48&type=cafe&type=restaurant&limit=50'
```

`bbox` is `min_lon,min_lat,max_lon,max_lat` (WGS 84). `type` is the OSM tag
value (`cafe`, `park`, `pharmacy`, ...) and can be repeated.

### `GET /places/near`: places within a radius, nearest first

```bash
curl 'localhost:8000/places/near?lat=48.4647&lon=35.0462&radius=500&type=cafe'
```

`radius` is in meters (up to 50 km). Each feature gets a `distance_m` property.

### Response

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "node/123456",
      "geometry": { "type": "Point", "coordinates": [35.0462, 48.4647] },
      "properties": {
        "osm_type": "node",
        "osm_id": 123456,
        "osm_url": "https://www.openstreetmap.org/node/123456",
        "category": "amenity",
        "kind": "cafe",
        "name": "...",
        "names": { "uk": "...", "en": "..." },
        "area_m2": null,
        "tags": { "amenity": "cafe", "opening_hours": "..." },
        "distance_m": 87.4
      }
    }
  ]
}
```

## Data

- **Source:** the [Geofabrik](https://download.geofabrik.de/europe/ukraine.html)
  extract of OpenStreetMap for Ukraine.
- **Places:** objects tagged `amenity`, `shop`, `tourism` or `leisure`, from
  nodes, ways and multipolygon relations. Street furniture such as benches and
  waste baskets is skipped.
- **Administrative boundaries:** oblasts (`admin_level=4`), raions (6) and
  cities, towns and villages (8).
- **Names:** `name`, `name:uk`, `name:en`, `name:ru`.
- **Regions:** the region is a parameter, not a constant. Bounding boxes live in
  [`etl/regions.py`](etl/regions.py). Any `.osm.pbf` file can also be loaded
  directly with `python -m etl load <file>`.

## Design decisions

- **One representative point per place.** Parks and buildings are polygons and
  tracks are lines, but search needs a single location. PostGIS computes
  `ST_PointOnSurface` on import, which always lies inside the shape (unlike the
  centroid of a C-shaped polygon). The full shape and its area in m² are kept
  as well.
- **Two GIST indexes on that point.** Bounding-box queries work in degrees and
  use the geometry index. Radius queries need meters, so they run on
  `geography(location)`, which has its own expression index. A test runs
  `EXPLAIN` on both API queries and fails if either stops using its index.
- **Idempotent batch loading.** Each batch of 5,000 rows is one
  `INSERT ... SELECT FROM unnest(...) ON CONFLICT DO UPDATE` statement keyed
  on the OSM id. A re-import updates rows in place, and an interrupted import
  can simply be restarted.
- **Small default region.** The Ukraine dump is filtered by tags once and the
  default region is cut out of it, so a local setup loads one city, not the
  whole country.

## Development

```bash
uv sync           # install dependencies
make test         # pytest; starts a throwaway PostGIS container, Docker required
make lint         # ruff + mypy (strict)
uv run pre-commit install
```

Tests run on a small synthetic OSM file ([`tests/fixtures/sample.osm`](tests/fixtures/sample.osm))
through the real ETL and a real PostGIS. No downloads are needed.

```
app/
  api/            FastAPI routers and dependencies
  services/       business logic, GeoJSON assembly
  repositories/   SQL queries
  models/         SQLAlchemy models
  schemas/        Pydantic request/response models
etl/              OSM download, extract and batch loading (python -m etl)
migrations/       Alembic migrations
tests/
```

## Roadmap

- [x] Data model, ETL from OSM, geo endpoints, Docker
- [ ] `POST /search`: plain-language queries parsed by an LLM into a typed
      filter (structured outputs), search inside cities by administrative
      boundaries, Redis cache, CI
- [ ] Whole-country import, GIST benchmarks, Leaflet map, demo

## License and attribution

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
