"""Minimal GeoJSON models (RFC 7946) for API responses."""

from typing import Literal

from pydantic import BaseModel


class Point(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]  # lon, lat


class Feature[P: BaseModel](BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: Point
    properties: P


class FeatureCollection[P: BaseModel](BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature[P]]
