"""Generate deterministic synthetic logistics/freight data as parquet.

Tables:
  carriers(carrier_id, carrier_name, mode, on_time_rate)
  lanes(lane_id, origin, destination, miles)
  shipments(shipment_id, carrier_id, lane_id, ship_date, weight_lbs, cost_usd, delivered_on_time)
"""

from __future__ import annotations

import os

import duckdb

HERE = os.path.dirname(__file__)


def main() -> None:
    con = duckdb.connect()
    con.execute("SELECT setseed(0.42)")

    con.execute(
        """
        CREATE TABLE carriers AS
        SELECT
            i AS carrier_id,
            'Carrier_' || i AS carrier_name,
            ['LTL', 'FTL', 'Parcel', 'Intermodal'][1 + (i % 4)] AS mode,
            round(0.80 + (i % 20) / 100.0, 3) AS on_time_rate
        FROM range(1, 13) t(i)
        """
    )
    con.execute(
        """
        CREATE TABLE lanes AS
        SELECT
            i AS lane_id,
            ['Toronto', 'Chicago', 'Dallas', 'Newark', 'Atlanta', 'Denver'][1 + (i % 6)] AS origin,
            ['Montreal', 'Detroit', 'Houston', 'Boston', 'Miami', 'Phoenix'][1 + (i % 6)] AS destination,
            200 + (i * 37) % 2200 AS miles
        FROM range(1, 25) t(i)
        """
    )
    con.execute(
        """
        CREATE TABLE shipments AS
        SELECT
            i AS shipment_id,
            1 + (i % 12) AS carrier_id,
            1 + (i % 24) AS lane_id,
            DATE '2026-01-01' + CAST((i * 7) % 180 AS INTEGER) AS ship_date,
            500 + (i * 113) % 19500 AS weight_lbs,
            round(150 + ((i * 91) % 4800) / 1.0, 2) AS cost_usd,
            ((i * 17) % 100) < 88 AS delivered_on_time
        FROM range(1, 5001) t(i)
        """
    )

    for table in ("carriers", "lanes", "shipments"):
        out = os.path.join(HERE, f"{table}.parquet")
        con.execute(f"COPY {table} TO '{out}' (FORMAT parquet)")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
