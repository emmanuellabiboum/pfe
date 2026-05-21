from pathlib import Path
import re

path = Path(__file__).resolve().parent.parent / "logs" / "django.log"
text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
keywords = [
    'GET /notifications/ HTTP/1.1" 500',
    "Internal Server Error: /notifications/",
    'GET /accounts/gestion-comptes/ HTTP/1.1" 500',
    "Internal Server Error: /accounts/gestion-comptes/",
    'GET /dashboard-global/ HTTP/1.1" 500',
    "Internal Server Error: /dashboard-global/",
]
for i, line in enumerate(text):
    if any(k in line for k in keywords):
        start = max(0, i - 10)
        end = min(len(text), i + 10)
        print("--- LINE", i + 1, "---")
        for j in range(start, end):
            print(f"{j+1}: {text[j]}")
        print()
