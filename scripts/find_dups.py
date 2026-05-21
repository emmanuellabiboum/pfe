import os, hashlib, json, sys

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ignore_dirs = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".uploads",
    "venv",
    "pfe_final/venv",
}
hash_map = {}
count = 0
for dirpath, dirnames, filenames in os.walk(root):
    # skip ignored dirs
    rel = os.path.relpath(dirpath, root)
    parts = set(p for p in rel.split(os.sep) if p)
    if parts & ignore_dirs:
        continue
    for fname in filenames:
        path = os.path.join(dirpath, fname)
        try:
            # skip very large files (>100MB)
            if os.path.getsize(path) > 100 * 1024 * 1024:
                continue
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            key = (h.hexdigest(), os.path.getsize(path))
            hash_map.setdefault(key, []).append(os.path.relpath(path, root))
            count += 1
        except Exception:
            continue

# collect duplicates
dups = []
for (digest, size), paths in hash_map.items():
    if len(paths) > 1:
        dups.append({"size": size, "hash": digest, "paths": paths})

dups.sort(key=lambda x: x["size"], reverse=True)
print(
    json.dumps(
        {"scanned_files": count, "duplicate_groups": dups}, ensure_ascii=False, indent=2
    )
)
