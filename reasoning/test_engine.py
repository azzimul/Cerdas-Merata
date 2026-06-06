"""
Quick test untuk reasoning engine — jalankan: python reasoning/test_engine.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from reasoning.engine import run, format_trace_human_readable

cases = [
    {
        "name": "Kasus 1 — Sangat Miskin, Yatim-Piatu, Berprestasi",
        "facts": {
            "pendapatan_ortu": 0,
            "jumlah_tanggungan": 4,
            "tagihan_listrik": 0,
            "wattage_listrik": 450,
            "ipk": 3.8,
            "status_ortu": "yatim_piatu",
            "pekerjaan_ortu": "tidak_bekerja",
            "bantuan_lain": False,
        },
    },
    {
        "name": "Kasus 2 — Menengah, IPK Rendah, Ada Beasiswa",
        "facts": {
            "pendapatan_ortu": 3500000,
            "jumlah_tanggungan": 2,
            "tagihan_listrik": 250000,
            "wattage_listrik": 1300,
            "ipk": 2.7,
            "status_ortu": "lengkap",
            "pekerjaan_ortu": "pns_swasta_tni",
            "bantuan_lain": True,
        },
    },
    {
        "name": "Kasus 3 — Anomali (450VA tapi pendapatan > 5 juta)",
        "facts": {
            "pendapatan_ortu": 6000000,
            "jumlah_tanggungan": 1,
            "tagihan_listrik": 50000,
            "wattage_listrik": 450,
            "ipk": 3.2,
            "status_ortu": "lengkap",
            "pekerjaan_ortu": "wiraswasta",
            "bantuan_lain": False,
        },
    },
    {
        "name": "Kasus 4 — Skala Nilai 100 (rapor SMA)",
        "facts": {
            "pendapatan_ortu": 1500000,
            "jumlah_tanggungan": 3,
            "tagihan_listrik": 120000,
            "wattage_listrik": 900,
            "ipk": 87.5,
            "status_ortu": "piatu",
            "pekerjaan_ortu": "buruh_petani",
            "bantuan_lain": False,
        },
    },
]

for case in cases:
    print(f"\n{'='*60}")
    print(f"  {case['name']}")
    print('='*60)
    result = run(case["facts"])
    print(format_trace_human_readable(result))
    print(f"\nSkor per kategori: {result.skor_per_kategori}")
