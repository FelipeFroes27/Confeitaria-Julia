from __future__ import annotations

import argparse
import unicodedata
from dataclasses import dataclass
from typing import Any

from services.google_sheets import GoogleSheetsClient


SOURCE_WORKSHEET = "RECEITAS"
TARGET_WORKSHEET = "RECEITAS ATUALIZADO"
MATERIALS_WORKSHEET = "BANCO DE DADOS "


# Variações antigas que representam com segurança uma matéria-prima cadastrada.
SAFE_ALIASES = {
    "chocolate ao leite": "chocolate ao leite tablete",
    "chocolate branco": "chocolate branco tablete",
    "chocolate meio amargo": "chocolate meio amargo tablete",
    "farinha": "farinha de trigo",
    "iogurte natural": "iogurt natural",
    "ninho": "leite em po",
    "ovos": "ovo",
}


@dataclass(frozen=True)
class Material:
    code: str
    name: str
    unit: str
    unit_cost: float | None


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_accents.split())


def normalize_unit(value: str) -> str:
    normalized = normalize_text(value)
    if normalized in {"un", "um", "unidade", "unidae"}:
        return "UN"
    return normalized


def parse_number(value: str) -> float | None:
    normalized = (
        value.strip()
        .replace("R$", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def load_materials(client: GoogleSheetsClient) -> dict[str, Material]:
    rows = client.worksheet(MATERIALS_WORKSHEET).get_all_values()[1:]
    materials: dict[str, Material] = {}
    for row in rows:
        if len(row) < 7:
            continue
        unit_cost = parse_number(row[6])
        if not row[0].strip() or not row[1].strip():
            continue
        material = Material(
            code=row[0].strip(),
            name=row[1].strip(),
            unit=normalize_unit(row[4]),
            unit_cost=unit_cost,
        )
        materials[normalize_text(material.name)] = material
    return materials


def source_recipe_headers(client: GoogleSheetsClient) -> list[tuple[int, int]]:
    metadata = client.spreadsheet().fetch_sheet_metadata()
    sheet_metadata = next(
        sheet
        for sheet in metadata["sheets"]
        if sheet["properties"]["title"] == SOURCE_WORKSHEET
    )
    headers = []
    for merged_range in sheet_metadata.get("merges", []):
        start_column = merged_range["startColumnIndex"]
        end_column = merged_range["endColumnIndex"]
        if (start_column, end_column) not in {(0, 4), (5, 9)}:
            continue
        headers.append((merged_range["startRowIndex"], start_column))
    return sorted(headers)


def build_migration_rows(
    client: GoogleSheetsClient,
) -> tuple[list[list[Any]], dict[str, Any]]:
    source_values = client.worksheet(SOURCE_WORKSHEET).get_all_values()
    materials = load_materials(client)
    rows_to_write: list[list[Any]] = []
    unmatched_names: set[str] = set()
    missing_quantity_count = 0
    matched_count = 0
    recipe_count = 0

    for recipe_code, (header_row, start_column) in enumerate(
        source_recipe_headers(client),
        start=1,
    ):
        padded_header = source_values[header_row] + [""] * 9
        recipe_name = padded_header[start_column].strip()
        if not recipe_name:
            continue
        recipe_count += 1

        current_row = header_row + 1
        while current_row < len(source_values):
            padded_row = source_values[current_row] + [""] * 9
            source_item = padded_row[start_column : start_column + 4]
            if not any(cell.strip() for cell in source_item):
                break

            legacy_name = source_item[0].strip()
            if not legacy_name:
                current_row += 1
                continue

            normalized_name = normalize_text(legacy_name)
            material_key = SAFE_ALIASES.get(normalized_name, normalized_name)
            material = materials.get(material_key)
            quantity = parse_number(source_item[1])

            if quantity is None:
                missing_quantity_count += 1

            if material is None:
                unmatched_names.add(legacy_name)
                material_code = ""
                material_name = legacy_name
                unit = normalize_unit(source_item[2])
                cost: float | str = ""
            else:
                matched_count += 1
                material_code = material.code
                material_name = material.name
                unit = material.unit
                cost = (
                    material.unit_cost * quantity
                    if material.unit_cost is not None and quantity is not None
                    else ""
                )

            rows_to_write.append(
                [
                    recipe_code,
                    recipe_name,
                    material_code,
                    material_name,
                    quantity if quantity is not None else "",
                    unit,
                    cost,
                    "0%",
                ]
            )
            current_row += 1

    report = {
        "recipes": recipe_count,
        "rows": len(rows_to_write),
        "matched_rows": matched_count,
        "unmatched_rows": len(rows_to_write) - matched_count,
        "missing_quantity_rows": missing_quantity_count,
        "unmatched_names": sorted(unmatched_names, key=str.casefold),
    }
    return rows_to_write, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Grava a migração; sem esta opção executa apenas a simulação.",
    )
    args = parser.parse_args()

    client = GoogleSheetsClient.from_streamlit_secrets()
    target = client.worksheet(TARGET_WORKSHEET)
    existing_rows = target.get_all_values()[1:]
    if existing_rows:
        raise RuntimeError(
            f"A aba {TARGET_WORKSHEET} já contém {len(existing_rows)} linhas. "
            "A migração foi interrompida para evitar duplicação."
        )

    rows, report = build_migration_rows(client)
    print(f"recipes={report['recipes']}")
    print(f"rows={report['rows']}")
    print(f"matched_rows={report['matched_rows']}")
    print(f"unmatched_rows={report['unmatched_rows']}")
    print(f"missing_quantity_rows={report['missing_quantity_rows']}")
    print(f"unmatched_names={report['unmatched_names']}")

    if not args.apply:
        print("mode=DRY_RUN")
        return

    for start in range(0, len(rows), 100):
        target.append_rows(
            rows[start : start + 100],
            value_input_option="USER_ENTERED",
        )
    print("mode=APPLIED")


if __name__ == "__main__":
    main()
