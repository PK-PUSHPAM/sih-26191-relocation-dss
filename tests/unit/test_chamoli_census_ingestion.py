import pandas as pd
import pytest

from scripts.ingest_chamoli_census import normalize_chamoli_population


def test_normalize_chamoli_population_filters_aggregates(monkeypatch, tmp_path):
    sheets = {
        "PCA TV": pd.DataFrame(
            {
                "Location Code": [
                    "05 057 00284 040808 0000",
                    "05 057 00284 040809 0000",
                    "05 057 00284 000000 0000",
                ],
                "Area Name": ["Mana", "Khiron", "Joshimath"],
                "Number of Households": ["558", "100", "7608"],
                "Population - Total": ["1214", "321", "29053"],
            }
        )
    }
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: sheets)

    result = normalize_chamoli_population(tmp_path / "source.xlsx")

    assert list(result["village_name"]) == ["Mana", "Khiron"]
    assert list(result["population_2011"]) == [1214, 321]
    assert list(result["households_2011"]) == [558, 100]
    assert set(result["source_id"]) == {"census_2011_basic_population_village"}


def test_missing_population_is_not_converted_to_zero(monkeypatch, tmp_path):
    sheets = {
        "PCA TV": pd.DataFrame(
            {
                "Location Code": ["05 057 00284 040808 0000"],
                "Area Name": ["Mana"],
                "Number of Households": ["558"],
                "Population - Total": [None],
            }
        )
    }
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: sheets)

    with pytest.raises(ValueError, match="missing records"):
        normalize_chamoli_population(tmp_path / "source.xlsx")


def test_duplicate_location_codes_are_rejected(monkeypatch, tmp_path):
    sheets = {
        "PCA TV": pd.DataFrame(
            {
                "Location Code": [
                    "05 057 00284 040808 0000",
                    "05 057 00284 040808 0000",
                ],
                "Area Name": ["Mana", "Mana Duplicate"],
                "Number of Households": ["558", "558"],
                "Population - Total": ["1214", "1214"],
            }
        )
    }
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: sheets)

    with pytest.raises(ValueError, match="Duplicate"):
        normalize_chamoli_population(tmp_path / "source.xlsx")
