"""Issue #5 - Add reference data: stores, suppliers and products.

As a data engineer, I want reference lists of stores, suppliers and products, with each
product's shelf life and an "essential" flag, so that the pipeline can check every delivery
and shelf check against them.

These tests check YOUR files in data/reference/. Shelf checks point to committee members and
trips point to vehicles, so the folder also needs committee_members.csv and vehicles.csv.
Checked by hand: the README says the store names are made up.
"""

import pytest

from helpers import PROJECT_DIR, REFERENCE_COLUMNS, count_rows, need, need_file, read_csv, read_header

pytestmark = pytest.mark.issue(5)

FILES = ["stores", "suppliers", "products", "committee_members", "vehicles"]
ID_COLUMNS = {
    "stores": "store_id",
    "suppliers": "supplier_id",
    "products": "product_id",
    "committee_members": "member_id",
    "vehicles": "vehicle_id",
}


def reference(name):
    return read_csv(need_file(f"data/reference/{name}.csv", issue=5))


@pytest.mark.parametrize("name", FILES)
def test_each_reference_file_has_the_expected_columns(name):
    path = need_file(f"data/reference/{name}.csv", issue=5)
    assert read_header(path) == REFERENCE_COLUMNS[name]


@pytest.mark.parametrize("name", FILES)
def test_ids_are_unique_and_filled_in(name):
    ids = [row[ID_COLUMNS[name]].strip() for row in reference(name)]
    assert all(ids), f"{name}.csv has a row without an ID"
    assert len(ids) == len(set(ids)), f"{name}.csv has the same ID more than once"


def test_at_least_8_made_up_stores_across_tembisa_sections():
    stores = reference("stores")
    assert len(stores) >= 8
    assert len({store["section"] for store in stores}) >= 3, "spread the stores across at least 3 sections"


def test_at_least_5_suppliers():
    assert len(reference("suppliers")) >= 5


def test_at_least_15_products():
    assert len(reference("products")) >= 15


def test_every_product_has_a_shelf_life_in_whole_days_above_zero():
    for product in reference("products"):
        assert product["shelf_life_days"].isdigit() and int(product["shelf_life_days"]) > 0, product


def test_essential_and_cold_storage_flags_are_1_or_0():
    for product in reference("products"):
        assert product["is_essential"] in ("0", "1"), product
        assert product["needs_cold_storage"] in ("0", "1"), product


@pytest.mark.parametrize("essential", ["bread", "milk", "maize", "egg", "drink"])
def test_essentials_include_bread_milk_maize_meal_eggs_and_cold_drinks(essential):
    essentials = [p for p in reference("products") if p["is_essential"] == "1"]
    words = " ".join(f"{p['product_name']} {p['category']}".lower() for p in essentials)
    assert essential in words, f"no essential product mentions {essential!r}"


def test_every_vehicle_belongs_to_a_known_supplier():
    suppliers = {row["supplier_id"] for row in reference("suppliers")}
    for vehicle in reference("vehicles"):
        assert vehicle["supplier_id"] in suppliers, vehicle


def test_committee_members_are_recorded_by_initials_and_section_only():
    for member in reference("committee_members"):
        assert len(member["initials"]) <= 6, f"use initials, not a full name: {member}"


def test_a_script_loads_the_reference_data_into_the_database(database):
    connect = need("safeshelf.db", "connect", issue=4)
    create_schema = need("safeshelf.db", "create_schema", issue=4)
    load_reference_data = need("safeshelf.db", "load_reference_data", issue=5)
    for name in FILES:
        need_file(f"data/reference/{name}.csv", issue=5)

    conn = connect()
    create_schema(conn)
    load_reference_data(conn, PROJECT_DIR / "data" / "reference")

    for name in FILES:
        assert count_rows(conn, name) == len(reference(name)), name
    conn.close()
