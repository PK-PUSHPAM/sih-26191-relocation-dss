#!/usr/bin/env python3
"""
Verify the live PostGIS state of the verified Chamoli habitation load.

This is a read-only verification tool. It does not mutate the database and
does not calculate any DSS outputs.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import text

from src.db.session import get_db


EXPECTED_HABITATIONS = 1174
EXPECTED_VILLAGES = 1174
EXPECTED_SRID = 32644


def main() -> int:
    with get_db() as session:
        counts = session.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM habitation) AS habitations,
                    (SELECT COUNT(*) FROM admin_unit WHERE type = 'village') AS villages,
                    (SELECT COUNT(*) FROM habitation WHERE geom IS NULL) AS null_geometry,
                    (SELECT COUNT(*) FROM habitation
                     WHERE NOT ST_IsValid(geom)) AS invalid_geometry,
                    (SELECT COUNT(*) FROM habitation
                     WHERE ST_SRID(geom) <> :srid) AS non_expected_srid
                """
            ),
            {"srid": EXPECTED_SRID},
        ).mappings().one()

        sample = session.execute(
            text(
                """
                SELECT habitation_id, name, population, households,
                       ST_SRID(geom) AS srid,
                       ST_GeometryType(geom) AS geom_type
                FROM habitation
                ORDER BY habitation_id
                LIMIT 5
                """
            )
        ).mappings().all()

    failures = []
    if counts["habitations"] != EXPECTED_HABITATIONS:
        failures.append(
            f"expected {EXPECTED_HABITATIONS} habitations, got {counts['habitations']}"
        )
    if counts["villages"] != EXPECTED_VILLAGES:
        failures.append(
            f"expected {EXPECTED_VILLAGES} village admin units, got {counts['villages']}"
        )
    if counts["null_geometry"] != 0:
        failures.append(f"{counts['null_geometry']} habitation geometries are NULL")
    if counts["invalid_geometry"] != 0:
        failures.append(f"{counts['invalid_geometry']} habitation geometries are invalid")
    if counts["non_expected_srid"] != 0:
        failures.append(
            f"{counts['non_expected_srid']} habitation geometries do not use SRID {EXPECTED_SRID}"
        )

    print("Chamoli PostGIS verification")
    print(f"  habitations:       {counts['habitations']}")
    print(f"  village admin:     {counts['villages']}")
    print(f"  null geometry:     {counts['null_geometry']}")
    print(f"  invalid geometry:  {counts['invalid_geometry']}")
    print(f"  non-{EXPECTED_SRID}:        {counts['non_expected_srid']}")
    print("  sample:")

    for row in sample:
        print(
            f"    {row['habitation_id']} | {row['name']} | "
            f"population={row['population']} | households={row['households']} | "
            f"SRID={row['srid']} | {row['geom_type']}"
        )

    if failures:
        print("VERIFICATION FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
