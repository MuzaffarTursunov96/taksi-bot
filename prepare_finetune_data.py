"""training_data.jsonl faylini OpenAI fine-tuning formatiga o'tkazadi.

Ishga tushirish: venv/bin/python prepare_finetune_data.py
Natija: finetune_train.jsonl va finetune_valid.jsonl fayllari yaratiladi.
"""

import json
import random
from pathlib import Path

from filters import build_system_prompt

SOURCE_PATH = Path("training_data.jsonl")
TRAIN_PATH = Path("finetune_train.jsonl")
VALID_PATH = Path("finetune_valid.jsonl")

VALID_RATIO = 0.1  # 10% tekshiruv (validation) uchun ajratiladi
REQUIRED_KEYS = {"is_route", "from", "to", "phone", "author_role"}


def _clean_label(label: dict) -> dict | None:
    if not isinstance(label, dict) or "is_route" not in label:
        return None
    return {key: label.get(key) if key != "is_route" else bool(label.get("is_route")) for key in REQUIRED_KEYS}


def main() -> None:
    if not SOURCE_PATH.exists():
        print(f"Xato: {SOURCE_PATH} topilmadi.")
        return

    system_prompt = build_system_prompt()

    # Bir xil matn bir necha marta uchrashi mumkin (backfill qayta ishga tushirilgan
    # bo'lsa) — faqat oxirgi (eng yangi) yozuvni qoldiramiz.
    by_text: dict[str, dict] = {}
    total_lines = 0
    with open(SOURCE_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = row.get("text")
            label = _clean_label(row.get("label"))
            if not text or label is None:
                continue
            by_text[text] = label

    examples = list(by_text.items())
    random.shuffle(examples)

    split_at = max(1, int(len(examples) * (1 - VALID_RATIO)))
    train_examples = examples[:split_at]
    valid_examples = examples[split_at:]

    def write_split(path: Path, rows: list[tuple[str, dict]]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for text, label in rows:
                record = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f'Xabar: """{text}"""'},
                        {"role": "assistant", "content": json.dumps(label, ensure_ascii=False)},
                    ]
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_split(TRAIN_PATH, train_examples)
    write_split(VALID_PATH, valid_examples)

    print(f"Jami qatorlar: {total_lines}")
    print(f"Noyob (takrorsiz) misollar: {len(examples)}")
    print(f"Train: {len(train_examples)} -> {TRAIN_PATH}")
    print(f"Valid: {len(valid_examples)} -> {VALID_PATH}")

    if len(examples) < 50:
        print(
            "\n⚠️ Diqqat: misollar soni kam (50 dan kam). Fine-tuning ishlaydi, "
            "lekin sifat past bo'lishi mumkin — ko'proq ma'lumot yig'ish tavsiya etiladi."
        )


if __name__ == "__main__":
    main()
