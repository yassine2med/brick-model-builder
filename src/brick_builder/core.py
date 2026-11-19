"""Turn an equipment spreadsheet into a Brick Schema model in Turtle."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

BRICK = "https://brickschema.org/schema/Brick#"
BASE = "https://example.org/building#"

# Spreadsheet label (lower case) -> Brick class
CLASS_MAP: dict[str, str] = {
    "building": "Building",
    "floor": "Floor",
    "room": "Room",
    "hvac zone": "HVAC_Zone",
    "ahu": "Air_Handling_Unit",
    "vav": "Variable_Air_Volume_Box",
    "chiller": "Chiller",
    "boiler": "Boiler",
    "pump": "Pump",
    "fan": "Fan",
    "supply air temp sensor": "Supply_Air_Temperature_Sensor",
    "zone temp sensor": "Zone_Air_Temperature_Sensor",
    "zone temp setpoint": "Zone_Air_Temperature_Setpoint",
}

ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class ModelError(ValueError):
    """Raised with every problem found in the spreadsheet, one per line."""


@dataclass(frozen=True)
class Entity:
    """One row of the spreadsheet."""

    id: str
    label: str
    brick_class: str
    part_of: str
    location: str
    feeds: tuple[str, ...]
    point_of: str


def read_entities(path: str | Path) -> list[Entity]:
    """Read and validate the spreadsheet. Raises ModelError listing all problems."""
    entities: list[Entity] = []
    errors: list[str] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            eid = (row.get("id") or "").strip()
            kind = (row.get("type") or "").strip().lower()
            if not ID_PATTERN.match(eid):
                errors.append(f"line {line_no}: bad id {eid!r} (letters, digits, _ and - only, start with a letter)")
                continue
            if kind not in CLASS_MAP:
                errors.append(f"line {line_no}: unknown type {row.get('type')!r} for {eid}")
                continue
            entities.append(
                Entity(
                    id=eid,
                    label=(row.get("label") or eid).strip(),
                    brick_class=CLASS_MAP[kind],
                    part_of=(row.get("part_of") or "").strip(),
                    location=(row.get("location") or "").strip(),
                    feeds=tuple(x.strip() for x in (row.get("feeds") or "").split(";") if x.strip()),
                    point_of=(row.get("point_of") or "").strip(),
                )
            )
    errors.extend(check_references(entities))
    if errors:
        raise ModelError("\n".join(errors))
    return entities


def check_references(entities: list[Entity]) -> list[str]:
    """Find duplicate ids, links to ids that do not exist and links to self."""
    errors: list[str] = []
    ids: set[str] = set()
    for e in entities:
        if e.id in ids:
            errors.append(f"duplicate id {e.id}")
        ids.add(e.id)
    for e in entities:
        links = [("part_of", e.part_of), ("location", e.location), ("point_of", e.point_of)]
        links += [("feeds", target) for target in e.feeds]
        for column, target in links:
            if not target:
                continue
            if target == e.id:
                errors.append(f"{e.id}: {column} points to itself")
            elif target not in ids:
                errors.append(f"{e.id}: {column} refers to unknown id {target}")
    return errors


def to_turtle(entities: list[Entity]) -> str:
    """Render the entities as Turtle, with each relationship written in both directions."""
    lines = [
        f"@prefix brick: <{BRICK}> .",
        f"@prefix bldg: <{BASE}> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
    ]
    for e in entities:
        label = e.label.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'bldg:{e.id} a brick:{e.brick_class} ; rdfs:label "{label}" .')
    lines.append("")
    for e in entities:
        if e.part_of:
            lines.append(f"bldg:{e.id} brick:isPartOf bldg:{e.part_of} .")
            lines.append(f"bldg:{e.part_of} brick:hasPart bldg:{e.id} .")
        if e.location:
            lines.append(f"bldg:{e.id} brick:hasLocation bldg:{e.location} .")
            lines.append(f"bldg:{e.location} brick:isLocationOf bldg:{e.id} .")
        for target in e.feeds:
            lines.append(f"bldg:{e.id} brick:feeds bldg:{target} .")
            lines.append(f"bldg:{target} brick:isFedBy bldg:{e.id} .")
        if e.point_of:
            lines.append(f"bldg:{e.point_of} brick:hasPoint bldg:{e.id} .")
            lines.append(f"bldg:{e.id} brick:isPointOf bldg:{e.point_of} .")
    return "\n".join(lines) + "\n"


def count_triples(turtle: str) -> int:
    """Parse the Turtle with rdflib and return the number of triples. Raises on bad syntax."""
    from rdflib import Graph

    graph = Graph()
    graph.parse(data=turtle, format="turtle")
    return len(graph)
