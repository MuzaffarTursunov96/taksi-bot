"""finetune_train.jsonl / finetune_valid.jsonl fayllarini OpenAI'ga yuklab,
fine-tuning jarayonini boshlaydi.

Ishga tushirish: venv/bin/python start_finetune.py
"""

import time
from pathlib import Path

from openai import OpenAI

from config import OPENAI_API_KEY

BASE_MODEL = "gpt-4o-mini-2024-07-18"

TRAIN_PATH = Path("finetune_train.jsonl")
VALID_PATH = Path("finetune_valid.jsonl")


def main() -> None:
    if not TRAIN_PATH.exists():
        print(f"Xato: {TRAIN_PATH} topilmadi. Avval prepare_finetune_data.py ni ishga tushiring.")
        return

    client = OpenAI(api_key=OPENAI_API_KEY)

    print("Fayllar yuklanmoqda...")
    train_file = client.files.create(file=open(TRAIN_PATH, "rb"), purpose="fine-tune")
    print(f"Train fayl yuklandi: {train_file.id}")

    valid_file_id = None
    if VALID_PATH.exists():
        valid_file = client.files.create(file=open(VALID_PATH, "rb"), purpose="fine-tune")
        valid_file_id = valid_file.id
        print(f"Valid fayl yuklandi: {valid_file.id}")

    print(f"Fine-tuning boshlanmoqda (asosiy model: {BASE_MODEL})...")
    job_kwargs = {"training_file": train_file.id, "model": BASE_MODEL}
    if valid_file_id:
        job_kwargs["validation_file"] = valid_file_id

    job = client.fine_tuning.jobs.create(**job_kwargs)
    print(f"\n✅ Fine-tuning job yaratildi: {job.id}")
    print("Holatni kuzatish uchun quyidagini ishga tushiring:")
    print(f"  python check_finetune.py {job.id}")

    print("\nYoki shu yerda kuzatib turaylikmi? Har 30 soniyada tekshiramiz...")
    while True:
        time.sleep(30)
        job = client.fine_tuning.jobs.retrieve(job.id)
        print(f"[{time.strftime('%H:%M:%S')}] Holat: {job.status}")
        if job.status in ("succeeded", "failed", "cancelled"):
            break

    if job.status == "succeeded":
        print(f"\n🎉 Tugadi! Yangi model nomi:\n{job.fine_tuned_model}")
        print("\nBuni serverdagi .env fayliga qo'shing:")
        print(f"OPENAI_MODEL={job.fine_tuned_model}")
    else:
        print(f"\n❌ Fine-tuning muvaffaqiyatsiz tugadi: {job.status}")
        if job.error:
            print(job.error)


if __name__ == "__main__":
    main()
