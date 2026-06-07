"""
Forward Chaining Reasoning Engine — Cerdas Merata v1.3
Membaca rules dari rules.json, mengevaluasi fakta siswa, menghasilkan skor + reasoning trace.
"""

import json
import os
from dataclasses import dataclass, field

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


@dataclass
class ReasoningResult:
    total_skor: int
    skor_per_kategori: dict[str, int]
    reasoning_trace: list[dict]
    is_anomaly: bool
    anomaly_reasons: list[str]
    status_keputusan: str = "pending"


def _load_rules() -> dict:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_ipk_100scale(ipk: float) -> bool:
    return ipk > 4.0


def _evaluate_condition(condition: dict, facts: dict) -> bool:
    field_name = condition["field"]
    op = condition["op"]
    val = facts.get(field_name)

    if val is None:
        return False

    if op == "eq":
        return val == condition["value"]
    elif op == "lt":
        return val < condition["value"]
    elif op == "gt":
        return val > condition["value"]
    elif op == "lte":
        return val <= condition["value"]
    elif op == "gte":
        return val >= condition["value"]
    elif op == "between":
        return condition["min"] <= val <= condition["max"]
    elif op == "in":
        return val in condition["values"]
    elif op == "gte_scaled":
        if _is_ipk_100scale(val):
            return val >= condition["value_100scale"]
        return val >= condition["value_4scale"]
    elif op == "between_scaled":
        if _is_ipk_100scale(val):
            return condition["min_100scale"] <= val <= condition["max_100scale"]
        return condition["min_4scale"] <= val <= condition["max_4scale"]

    return False


def _check_anomalies(anomaly_rules: list[dict], facts: dict) -> tuple[bool, list[str]]:
    triggered = []
    for rule in anomaly_rules:
        if all(_evaluate_condition(c, facts) for c in rule["conditions"]):
            triggered.append(f"[{rule['id']}] {rule['description']}")
    return bool(triggered), triggered


def _apply_exclusive_groups(fired_rule_ids: list[str], groups: list[list[str]]) -> list[str]:
    """
    Dalam setiap exclusive group, hanya rule pertama yang terpicu yang dihitung.
    Ini memastikan hanya satu tier per kategori yang aktif.
    """
    excluded = set()
    for group in groups:
        first_hit = None
        for rule_id in group:
            if rule_id in fired_rule_ids and first_hit is None:
                first_hit = rule_id
            elif rule_id in fired_rule_ids and first_hit is not None:
                excluded.add(rule_id)
    return [r for r in fired_rule_ids if r not in excluded]


def run(facts: dict) -> ReasoningResult:
    """
    Jalankan forward chaining terhadap satu set fakta pendaftar.

    Args:
        facts: dict dengan key sesuai field aplikasi:
            - pendapatan_ortu: int (Rp)
            - jumlah_tanggungan: int
            - tagihan_listrik: int (Rp)
            - wattage_listrik: int (VA)
            - ipk: float (skala 4.0 atau 0-100)
            - status_ortu: str ('lengkap'|'yatim'|'piatu'|'yatim_piatu')
            - pekerjaan_ortu: str ('tidak_bekerja'|'buruh_petani'|'pedagang_kecil'|'wiraswasta'|'pns_swasta_tni')
            - bantuan_lain: bool

    Returns:
        ReasoningResult dengan skor, trace, dan flag anomali
    """
    ruleset = _load_rules()

    is_anomaly, anomaly_reasons = _check_anomalies(ruleset["anomaly_rules"], facts)

    all_rules = ruleset["rules"]
    exclusive_groups = ruleset["exclusive_category_groups"]

    fired_ids_all = []
    rule_map = {}
    for rule in all_rules:
        if _evaluate_condition(rule["condition"], facts):
            fired_ids_all.append(rule["id"])
        rule_map[rule["id"]] = rule

    fired_ids = _apply_exclusive_groups(fired_ids_all, exclusive_groups)

    skor_per_kategori = {cat: 0 for cat in ruleset["categories"]}
    reasoning_trace = []

    for rule_id in fired_ids:
        rule = rule_map[rule_id]
        cat = rule["category"]
        pts = rule["points"]
        skor_per_kategori[cat] += pts
        reasoning_trace.append({
            "rule_id": rule_id,
            "category": cat,
            "description": rule["description"],
            "label": rule["label"],
            "points": pts
        })

    total_skor = sum(skor_per_kategori.values())

    return ReasoningResult(
        total_skor=total_skor,
        skor_per_kategori=skor_per_kategori,
        reasoning_trace=reasoning_trace,
        is_anomaly=is_anomaly,
        anomaly_reasons=anomaly_reasons,
    )


def format_trace_human_readable(result: ReasoningResult) -> str:
    """Hasilkan reasoning trace yang bisa dibaca pengguna awam."""
    lines = ["=== HASIL PENILAIAN KELAYAKAN ===\n"]

    category_labels = {
        "kemiskinan": "Kategori A — Kemiskinan",
        "tanggungan": "Kategori B — Tanggungan Keluarga",
        "infrastruktur": "Kategori C — Infrastruktur & Keterbatasan Ekonomi",
        "sosial": "Kategori D — Kondisi Sosial & Keluarga",
        "prestasi": "Kategori E — Prestasi Akademik & Pengurang",
    }

    trace_by_cat: dict[str, list] = {cat: [] for cat in category_labels}
    for entry in result.reasoning_trace:
        trace_by_cat[entry["category"]].append(entry)

    for cat, label in category_labels.items():
        entries = trace_by_cat[cat]
        cat_score = result.skor_per_kategori[cat]
        if entries:
            lines.append(f"{label}: {'+' if cat_score >= 0 else ''}{cat_score} poin")
            for e in entries:
                sign = "+" if e["points"] >= 0 else ""
                lines.append(f"  >> [{e['rule_id']}] {e['description']} -> {sign}{e['points']} poin ({e['label']})")
        else:
            lines.append(f"{label}: 0 poin (tidak ada aturan yang aktif)")
        lines.append("")

    lines.append(f"TOTAL SKOR: {result.total_skor} poin")

    if result.is_anomaly:
        lines.append("\n[!] ANOMALI TERDETEKSI -- Memerlukan Review Manual:")
        for reason in result.anomaly_reasons:
            lines.append(f"  * {reason}")

    return "\n".join(lines)
