#!/usr/bin/env python3
"""
Cerdas Merata — Demo Data Generator

Generates randomised scholarship application records and writes them to CSV.
The output CSV can be imported directly via the Admin → Import CSV feature.

Usage:
  python generate_data.py                      # 50 records → demo_applicants.csv
  python generate_data.py --count 100          # 100 records
  python generate_data.py -n 30 -o batch.csv  # 30 records → batch.csv
  python generate_data.py --seed 42            # reproducible output
"""

import argparse
import csv
import random
import sys

# ── Name pool ────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Ahmad", "Budi", "Cahya", "Dewi", "Eko", "Fajar", "Galuh", "Hani",
    "Irfan", "Joko", "Karina", "Lina", "Muhammad", "Nurul", "Oki", "Putri",
    "Rafi", "Sari", "Taufik", "Umar", "Vina", "Wahyu", "Yusuf", "Zahra",
    "Agus", "Bagas", "Citra", "Dani", "Endah", "Fauzi", "Gilang", "Hendra",
    "Ika", "Jaya", "Kurnia", "Laila", "Mira", "Nanda", "Omar", "Prita",
    "Rendra", "Sinta", "Tari", "Ulfa", "Vian", "Winda", "Yanuar", "Zulfa",
    "Arif", "Bella", "Chandra", "Dina", "Edy", "Fitri", "Guntur", "Hesti",
    "Iwan", "Juni", "Krisna", "Lilis", "Mario", "Nina", "Prasetyo", "Rani",
    "Surya", "Tri", "Utami", "Veri", "Wati", "Yoga", "Ardi", "Bunga",
    "Dimas", "Elsa", "Faris", "Gita", "Hafiz", "Indah", "Jasmine", "Kevin",
]

LAST_NAMES = [
    "Santoso", "Wijaya", "Setiawan", "Prasetyo", "Kusuma", "Nugroho",
    "Wibowo", "Saputra", "Purnomo", "Hartono", "Susanto", "Rahayu",
    "Budiman", "Permana", "Hidayat", "Sukardi", "Firmansyah", "Hakim",
    "Kurniawan", "Anwar", "Basuki", "Darmawan", "Effendi", "Gunawan",
    "Hadiyanto", "Indrajaya", "Junaedi", "Kamaludin", "Lutfi", "Maulana",
    "Natsir", "Oktavian", "Pujianto", "Qodir", "Ruslan", "Suherman",
    "Tamara", "Utomo", "Valentino", "Widodo", "Yuliana", "Zamzami",
]

# ── Field value pools with realistic weights ──────────────────────────────────

INCOME = {
    "values":  [0, 500_000, 1_500_000, 2_500_000, 3_750_000, 5_000_000],
    "weights": [0.07, 0.17, 0.27, 0.25, 0.15, 0.09],
}
DEPENDENTS = {
    "values":  [1, 2, 3, 4],
    "weights": [0.18, 0.34, 0.30, 0.18],
}
ELECTRICITY_BILL = {
    "values":  [0, 50_000, 150_000, 275_000, 400_000],
    "weights": [0.05, 0.20, 0.35, 0.25, 0.15],
}
WATTAGE = {
    "values":  [450, 900, 1300, 2200, 0],
    "weights": [0.15, 0.30, 0.30, 0.20, 0.05],
}
GPA = {
    "values":  [3.8, 3.6, 3.2, 2.7, 2.0],
    "weights": [0.12, 0.22, 0.35, 0.22, 0.09],
}
PARENT_STATUS = {
    "values":  ["lengkap", "yatim", "piatu", "yatim_piatu"],
    "weights": [0.70, 0.15, 0.10, 0.05],
}
PARENT_JOB = {
    "values":  ["tidak_bekerja", "buruh_petani", "pedagang_kecil", "wiraswasta", "pns_swasta_tni"],
    "weights": [0.10, 0.25, 0.25, 0.20, 0.20],
}

SPECIAL_CONDITIONS = [
    "Father recently lost his job due to factory closure.",
    "Currently living with grandparents after parents' divorce.",
    "Mother undergoing chemotherapy, significant medical expenses.",
    "Family home destroyed by flood, currently renting temporary housing.",
    "Sole breadwinner for younger siblings since father passed away.",
    "Has a chronic illness that limits ability to work part-time.",
    "Supporting an elderly grandparent with no pension income.",
    "Single-parent household; mother works as a domestic helper.",
    "Recently relocated from a remote village with no prior school support.",
    "Family lost their agricultural land due to a prolonged land dispute.",
    "Younger sibling has a disability requiring ongoing medical care.",
    "Father has been ill and unable to work for the past six months.",
]

COLUMNS = [
    "full_name",
    "pendapatan_ortu",
    "jumlah_tanggungan",
    "tagihan_listrik",
    "wattage_listrik",
    "ipk",
    "status_ortu",
    "pekerjaan_ortu",
    "bantuan_lain",
    "kondisi_khusus",
]


# ── Generator ─────────────────────────────────────────────────────────────────

def _pick(pool):
    return random.choices(pool["values"], weights=pool["weights"], k=1)[0]


def _random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _generate_row():
    income  = _pick(INCOME)
    wattage = _pick(WATTAGE)
    bill    = _pick(ELECTRICITY_BILL)

    # Correlation: no electricity → no bill
    if wattage == 0:
        bill = 0

    # Correlation: very low income tends toward low wattage
    if income == 0 and wattage not in (0, 450):
        wattage = random.choice([450, 0])
        if wattage == 0:
            bill = 0

    has_condition = random.random() < 0.12
    kondisi = random.choice(SPECIAL_CONDITIONS) if has_condition else ""

    return {
        "full_name":          _random_name(),
        "pendapatan_ortu":    income,
        "jumlah_tanggungan":  _pick(DEPENDENTS),
        "tagihan_listrik":    bill,
        "wattage_listrik":    wattage,
        "ipk":                _pick(GPA),
        "status_ortu":        _pick(PARENT_STATUS),
        "pekerjaan_ortu":     _pick(PARENT_JOB),
        "bantuan_lain":       "false" if random.random() < 0.85 else "true",
        "kondisi_khusus":     kondisi,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate randomised demo application data for Cerdas Merata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--count", "-n", type=int, default=100,
                        help="Number of records to generate (default: 100)")
    parser.add_argument("--output", "-o", default="demo_applicants.csv",
                        help="Output CSV filename (default: demo_applicants.csv)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible output")
    args = parser.parse_args()

    if args.count < 1:
        print("Error: --count must be at least 1", file=sys.stderr)
        sys.exit(1)

    if args.seed is not None:
        random.seed(args.seed)

    rows = [_generate_row() for _ in range(args.count)]

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {args.count} records  →  {args.output}")
    print()
    print("Import this file via Admin → Import CSV.")
    print("All imported accounts will have password:  Demo@1234")


if __name__ == "__main__":
    main()
