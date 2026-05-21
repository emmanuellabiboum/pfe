from pathlib import Path
import re

path = Path(__file__).resolve().parent.parent / "logs" / "django.log"
text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
keywords = [
    'GET /notifications/ HTTP/1.1" 500',
    "Internal Server Error: /notifications/",
    'GET /accounts/gestion-comptes/ HTTP/1.1" 500',
    "Internal Server Error: /accounts/gestion-comptes/",
]
count = 0
for i, line in enumerate(text):
    if any(k in line for k in keywords):
        count += 1
        start = max(0, i - 5)
        end = min(len(text), i + 5)
        print("--- MATCH", count, "AT LINE", i + 1, "---")
        for j in range(start, end):
            print(f"{j+1}: {text[j]}")
        print("")
        if count >= 5:
            break
