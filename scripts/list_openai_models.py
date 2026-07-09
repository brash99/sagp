from pathlib import Path
import os

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("OPENAI_API_KEY not found.")

client = OpenAI()

print("\nAvailable models:\n")

models = sorted(client.models.list().data, key=lambda m: m.id)

for model in models:
    print(model.id)
