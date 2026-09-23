"""AI'ga (OpenAI'ga) yuborilgan xabarlarni CSV qilib eksport qiladi — filtr
qo'shish uchun qo'lda ko'rib chiqish maqsadida.

Ishlatish: python export_ai_messages_csv.py [soatlar]
(standart: oxirgi 24 soat)
"""

import csv
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

TRAINING_DATA_PATH = Path(__file__).parent / "training_data.jsonl"
OUTPUT_PATH = Path(__file__).parent / "ai_messages_export.csv"


def main() -> None:
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 24
    cutoff = time.time() - hours * 3600

    rows = []
    with open(TRAINING_DATA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("ts", 0) < cutoff:
                continue
            label = entry.get("label") or {}
            rows.append(
                {
                    "vaqt": datetime.fromtimestamp(entry["ts"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "matn": entry.get("text", ""),
                    "is_route": label.get("is_route"),
                    "from": label.get("from"),
                    "to": label.get("to"),
                    "author_role": label.get("author_role"),
                }
            )

    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["vaqt", "matn", "is_route", "from", "to", "author_role"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} ta yozuv eksport qilindi -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
