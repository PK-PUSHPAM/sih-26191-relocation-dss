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


def test_basic_population_data_sheet_selects_only_chamoli_villages(monkeypatch, tmp_path):
    sheets = {
        "Data": pd.DataFrame(
            {
                "State": ["05", "05", "05", "06"],
                "District": ["057", "057", "057", "001"],
                "Subdistt": ["00284", "00284", "00000", "00001"],
                "Town/Village": ["040808", "040809", "000000", "000001"],
                "Ward": ["0000", "0000", "0000", "0000"],
                "Level": ["VILLAGE", "VILLAGE", "DISTRICT", "VILLAGE"],
                "Name": ["Mana", "Khiron", "Chamoli Total", "Other"],
                "TRU": ["Total", "Total", "Total", "Total"],
                "No_HH": ["558", "100", "88964", "10"],
                "TOT_P": ["1214", "321", "391605", "20"],
            }
        )
    }
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: sheets)

    result = normalize_chamoli_population(tmp_path / "source.xlsx")

    assert list(result["location_code"]) == [
        "05 057 00284 040808 0000",
        "05 057 00284 040809 0000",
    ]
    assert list(result["village_name"]) == ["Mana", "Khiron"]


def test_basic_population_workbook_without_villages_is_rejected(monkeypatch, tmp_path):
    sheets = {
        "Data": pd.DataFrame(
            {
                "State": ["05", "05"],
                "District": ["057", "057"],
                "Subdistt": ["00000", "00284"],
                "Town/Village": ["000000", "800290"],
                "Ward": ["0000", "0000"],
                "Level": ["DISTRICT", "TOWN"],
                "Name": ["Chamoli Total", "Badrinathpuri (NP)"],
                "TRU": ["Total", "Urban"],
                "No_HH": ["88964", "850"],
                "TOT_P": ["391605", "2438"],
            }
        )
    }
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: sheets)

    with pytest.raises(ValueError, match="no Chamoli village-level records"):
        normalize_chamoli_population(tmp_path / "source.xlsx")


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
