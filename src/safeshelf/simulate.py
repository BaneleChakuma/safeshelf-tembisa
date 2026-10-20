"""Simulate realistic daily data, with deliberate problems for the pipeline to catch. Issue #6.

    python -m safeshelf.simulate --days 30 --seed 42

There's no real data feed yet, so this writes one file per type per day into data/incoming,
using the made-up stores, suppliers and products in data/reference. The same seed always
gives exactly the same files.

On purpose, about 5 to 10% of rows are bad (missing fields, misspelled products, impossible
dates, unknown stores), some trucks arrive late or stop unexpectedly, some deliveries arrive
close to their expiry date, and old stock expires on the shelves.
"""

import argparse
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from safeshelf.extract import COLUMNS, FILE_TYPES
from safeshelf.settings import PROJECT_DIR

BAD_ROW_CHANCE = 0.07
UNRECOGNISABLE_PRODUCTS = ["Brd Whte", "Mlk 1L", "Choc Bar", "Bred", "Coldrink 2L??", "Mealie Maal"]
PRODUCTS_FROM_SUPPLIER = {  # supplier category -> product categories it delivers
    "bakery": {"bread"},
    "dairy": {"dairy", "eggs"},
    "drinks": {"drinks"},
    "wholesaler": {"grains", "eggs", "snacks", "drinks", "groceries"},
}
SPOILED = ["MOULDY", "DAMAGED_PACKAGING", "SWOLLEN"]
COMPLAINTS = {
    "EXPIRED": "Expired {product} on the shelf",
    "SPOILED": "The {product} was spoiled when I opened it",
    "BAD_SMELL": "The fridge section smells bad",
    "SICK_AFTER_EATING": "My child got sick after eating {product}",
    "OTHER": "Shelves are dirty and food is not covered",
}


def generate(root: str | Path, days: int, seed: int, start: date | None = None) -> list[Path]:
    """Write `days` days of data into <root>/data/incoming, starting on `start`.

    `start` defaults to the day that makes the last simulated day today. Returns the files written.
    """
    root = Path(root)
    start = start or date.today() - timedelta(days=days - 1)
    simulator = _Simulator(root / "data" / "reference", random.Random(seed))
    incoming = root / "data" / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)

    written = []
    for number in range(days):
        day = start + timedelta(days=number)
        rows = simulator.simulate_day(day)
        for file_type in FILE_TYPES:
            path = incoming / f"{file_type}_{day}.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=COLUMNS[file_type])
                writer.writeheader()
                writer.writerows(rows[file_type])
            written.append(path)
    return written


def _read_reference(folder: Path, name: str) -> list[dict[str, str]]:
    path = folder / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"reference file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as file:
        return [{key: value.strip() for key, value in row.items()} for row in csv.DictReader(file)]


def _at(day: date, minutes: int) -> datetime:
    """`minutes` after midnight on `day`."""
    return datetime.combine(day, datetime.min.time()) + timedelta(minutes=minutes)


class _Simulator:
    """Makes up one day of data at a time. All randomness comes from `rng`, so a seed repeats exactly."""

    def __init__(self, reference_folder: Path, rng: random.Random):
        self.rng = rng
        self.stores = _read_reference(reference_folder, "stores")
        self.suppliers = _read_reference(reference_folder, "suppliers")
        self.products = _read_reference(reference_folder, "products")
        self.members = _read_reference(reference_folder, "committee_members")
        self.vehicles = _read_reference(reference_folder, "vehicles")
        aliases = _read_reference(reference_folder, "product_aliases")
        self.aliases = {
            product["product_id"]: [a["alias"] for a in aliases if a["product_id"] == product["product_id"]]
            for product in self.products
        }
        self.stock = {store["store_id"]: [] for store in self.stores}  # (product, batch, expiry) per store

    # --- small helpers -----------------------------------------------------------------------

    def is_bad(self) -> bool:
        return self.rng.random() < BAD_ROW_CHANCE

    def timestamp(self, moment: datetime) -> str:
        """Usually the standard format, sometimes the way people type it."""
        if self.rng.random() < 0.1:
            return moment.strftime(self.rng.choice(["%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M"]))
        return moment.strftime("%Y-%m-%d %H:%M:%S")

    def date_text(self, day: date) -> str:
        return day.strftime("%d/%m/%Y") if self.rng.random() < 0.1 else day.isoformat()

    def location(self) -> tuple[str, str]:
        """Somewhere in and around Tembisa."""
        return f"{self.rng.uniform(-26.06, -25.96):.4f}", f"{self.rng.uniform(28.17, 28.26):.4f}"

    def product_text(self, product: dict) -> str:
        """Products are written in different ways: the name, an alias, or the name in lower case."""
        roll = self.rng.random()
        if roll < 0.2 and self.aliases[product["product_id"]]:
            return self.rng.choice(self.aliases[product["product_id"]])
        if roll < 0.3:
            return f"  {product['product_name'].lower()} "
        return product["product_name"]

    def products_from(self, supplier_id: str) -> list[dict]:
        category = next((s["category"].lower() for s in self.suppliers if s["supplier_id"] == supplier_id), "")
        wanted = PRODUCTS_FROM_SUPPLIER.get(category)
        return [p for p in self.products if wanted is None or p["category"].lower() in wanted] or self.products

    # --- one day -----------------------------------------------------------------------------

    def simulate_day(self, day: date) -> dict[str, list[dict]]:
        rows = {file_type: [] for file_type in FILE_TYPES}
        for number, vehicle in enumerate(self.vehicles):
            self.trip(day, number, vehicle, rows)

        suppliers_with_trucks = {vehicle["supplier_id"] for vehicle in self.vehicles}
        for supplier in self.suppliers:
            if supplier["supplier_id"] not in suppliers_with_trucks:  # delivers without a tracked truck
                store = self.rng.choice(self.stores)
                moment = _at(day, self.rng.randint(9 * 60, 15 * 60))
                delivery_id = f"D{day:%y%m%d}{supplier['supplier_id']}"
                self.delivery(day, delivery_id, store, supplier["supplier_id"], "", moment, rows)

        for member in self.members:
            self.shelf_checks(day, member, rows)
        for _ in range(self.rng.randint(0, 2)):
            self.community_report(day, rows)
        return rows

    def trip(self, day: date, number: int, vehicle: dict, rows: dict) -> None:
        """One truck trip: leave the depot, deliver to one or two stores, arrive."""
        rng = self.rng
        trip_id = f"T{day:%y%m%d}{vehicle['vehicle_id']}"
        planned_departure = _at(day, 6 * 60 + 30 * number + rng.choice([0, 15, 30]))
        planned_arrival = planned_departure + timedelta(minutes=rng.choice([180, 195, 210]))
        rows["trips"].append(
            {
                "trip_id": trip_id,
                "vehicle_id": vehicle["vehicle_id"],
                "planned_departure": f"{planned_departure:%Y-%m-%d %H:%M:%S}",
                "planned_arrival": f"{planned_arrival:%Y-%m-%d %H:%M:%S}",
            }
        )

        moment = planned_departure + timedelta(minutes=rng.randint(0, 10))
        updates = [(moment, "DEPARTED")]
        for stop in range(rng.randint(1, 2)):
            moment += timedelta(minutes=rng.randint(20, 30))
            updates.append((moment, "CHECKPOINT"))
            moment += timedelta(minutes=rng.randint(10, 20))
            updates.append((moment, "STOPPED"))  # unloading at a store
            delivered_at = moment + timedelta(minutes=rng.randint(3, 10))
            delivery_id = f"D{day:%y%m%d}{vehicle['vehicle_id']}{stop + 1}"
            store = rng.choice(self.stores)
            self.delivery(day, delivery_id, store, vehicle["supplier_id"], trip_id, delivered_at, rows)
            moment += timedelta(minutes=rng.randint(15, 25))
            updates.append((moment, "CHECKPOINT"))
        if rng.random() < 0.06:  # a stop with no delivery
            moment += timedelta(minutes=rng.randint(10, 20))
            updates.append((moment, "STOPPED"))
            moment += timedelta(minutes=rng.randint(15, 45))
            updates.append((moment, "CHECKPOINT"))
        if rng.random() < 0.15:  # a delayed truck
            arrival = planned_arrival + timedelta(minutes=rng.randint(35, 90))
        else:
            arrival = planned_arrival - timedelta(minutes=rng.randint(0, 20))
        updates.append((max(arrival, moment + timedelta(minutes=15)), "ARRIVED"))

        for moment, event_type in updates:
            latitude, longitude = self.location()
            row = {
                "trip_id": trip_id,
                "event_time": self.timestamp(moment),
                "event_type": event_type if rng.random() > 0.1 else event_type.lower(),
                "latitude": latitude,
                "longitude": longitude,
            }
            if self.is_bad():
                problem = rng.choice(["event_type", "latitude", "missing"])
                if problem == "event_type":
                    row["event_type"] = "PARKED"
                elif problem == "latitude":
                    row["latitude"] = rng.choice(["abc", "-95.0000"])
                else:
                    row[rng.choice(["event_time", "longitude"])] = ""
            rows["trip_events"].append(row)

    def delivery(self, day, delivery_id, store, supplier_id, trip_id, moment, rows) -> None:
        """One delivery to a store, with two to four items."""
        rng = self.rng
        rows["deliveries"].append(
            {
                "delivery_id": delivery_id,
                "store_id": store["store_id"],
                "supplier_id": supplier_id,
                "trip_id": trip_id,
                "delivered_at": self.timestamp(moment),
            }
        )
        for _ in range(rng.randint(2, 4)):
            product = rng.choice(self.products_from(supplier_id))
            shelf_life = int(product["shelf_life_days"])
            if rng.random() < 0.1:  # already old when it arrives
                age = rng.randint(shelf_life // 2 + 1, shelf_life)
            else:
                age = rng.randint(0, max(0, min(2, shelf_life // 4)))
            produced = day - timedelta(days=age)
            expires = produced + timedelta(days=shelf_life)
            batch = f"{product['category'][:1].upper()}{day:%m%d}-{rng.randint(100, 999)}"
            row = {
                "delivery_id": delivery_id,
                "product": self.product_text(product),
                "batch_code": batch,
                "quantity": str(rng.randint(6, 48)),
                "production_date": self.date_text(produced),
                "expiry_date": self.date_text(expires),
            }
            if self.is_bad():
                problem = rng.choice(["product", "quantity", "dates", "missing"])
                if problem == "product":
                    row["product"] = rng.choice(UNRECOGNISABLE_PRODUCTS)
                elif problem == "quantity":
                    row["quantity"] = rng.choice(["0", "-4", "lots"])
                elif problem == "dates":
                    row["expiry_date"] = (produced - timedelta(days=2)).isoformat()
                else:
                    row["batch_code"] = ""
            else:
                self.stock[store["store_id"]].append((product, batch, expires))
            rows["delivery_items"].append(row)

    def shelf_checks(self, day, member, rows) -> None:
        """A committee member checks two to four batches in a store in their section."""
        rng = self.rng
        local_stores = [store for store in self.stores if store["section"] == member["section"]]
        store = rng.choice(local_stores or self.stores)
        recent_stock = [item for item in self.stock[store["store_id"]] if (day - item[2]).days < 7]
        for _ in range(rng.randint(2, 4)):
            if recent_stock:
                product, batch, expires = rng.choice(recent_stock)
            else:
                product = rng.choice(self.products)
                batch = f"{product['category'][:1].upper()}{day:%m%d}-{rng.randint(100, 999)}"
                expires = day + timedelta(days=rng.randint(1, int(product["shelf_life_days"])))
            if expires < day:
                condition = "EXPIRED" if rng.random() < 0.8 else "OK"  # sometimes the member misses it
            elif rng.random() < 0.08:
                condition = "NOT_COLD" if product["needs_cold_storage"] == "1" else rng.choice(SPOILED)
            else:
                condition = "OK"
            row = {
                "store_id": store["store_id"] if rng.random() > 0.1 else f" {store['store_id'].lower()}",
                "product": self.product_text(product),
                "batch_code": batch,
                "expiry_date": self.date_text(expires),
                "quantity_on_shelf": str(rng.randint(1, 20)),
                "condition": condition if rng.random() > 0.1 else f" {condition.lower()}",
                "checked_at": self.timestamp(_at(day, rng.randint(8 * 60, 17 * 60))),
                "member_id": member["member_id"],
                "photo_ref": f"IMG_{day:%m%d}_{rng.randint(1000, 9999)}.jpg" if condition != "OK" else "",
            }
            if self.is_bad():
                problem = rng.choice(["store", "member", "condition", "quantity", "product", "expiry"])
                if problem == "store":
                    row["store_id"] = "ST99"
                elif problem == "member":
                    row["member_id"] = ""
                elif problem == "condition":
                    row["condition"] = "BROKEN"
                elif problem == "quantity":
                    row["quantity_on_shelf"] = "0"
                elif problem == "product":
                    row["product"] = rng.choice(UNRECOGNISABLE_PRODUCTS)
                else:
                    row["expiry_date"] = "31/02/2026"
            rows["shelf_checks"].append(row)
            if rng.random() < 0.03:  # sent twice by mistake
                rows["shelf_checks"].append(dict(row))

    def community_report(self, day, rows) -> None:
        """An anonymous report from a resident. Some people type their phone number in it."""
        rng = self.rng
        issue_type = rng.choice(list(COMPLAINTS))
        product = rng.choice(self.products) if rng.random() < 0.6 else None
        description = COMPLAINTS[issue_type].format(product=product["product_name"] if product else "food")
        if rng.random() < 0.15:
            description += f". Call me on 08{rng.randint(1, 4)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}"
        row = {
            "store_id": rng.choice(self.stores)["store_id"],
            "product": self.product_text(product) if product else "",
            "reported_at": self.timestamp(_at(day, rng.randint(7 * 60, 20 * 60))),
            "issue_type": issue_type,
            "description": description,
        }
        if self.is_bad():
            if rng.random() < 0.5:
                row["issue_type"] = "LATE"
            else:
                row["store_id"] = ""
        rows["community_reports"].append(row)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m safeshelf.simulate", description="Simulate daily SafeShelf data.")
    parser.add_argument("--days", type=int, default=30, help="how many days to simulate (default: 30)")
    parser.add_argument("--seed", type=int, default=42, help="the same seed always gives the same data (default: 42)")
    parser.add_argument("--start", type=date.fromisoformat, help="first day, YYYY-MM-DD (default: ends today)")
    parser.add_argument("--root", type=Path, default=PROJECT_DIR, help="the folder that holds data/")
    args = parser.parse_args(argv)
    written = generate(args.root, days=args.days, seed=args.seed, start=args.start)
    print(f"Wrote {len(written)} files to {args.root / 'data' / 'incoming'}")


if __name__ == "__main__":
    main()
