import os, json, subprocess, sys

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Run find_dups.py to get duplicate groups
proc = subprocess.run(
    [sys.executable, os.path.join("scripts", "find_dups.py")],
    capture_output=True,
    text=True,
)
if proc.returncode != 0:
    print("Error running find_dups.py", proc.stderr)
    sys.exit(1)
info = json.loads(proc.stdout)
removed = []
skipped = []
for grp in info.get("duplicate_groups", []):
    paths = grp["paths"]
    # Delete any copy inside pfe_final
    for p in paths:
        lp = p.replace("/", os.sep).replace("\\", os.sep)
        if "pfe_final" in lp.lower():
            if lp.lower().endswith(".exe"):
                skipped.append(lp)
                continue
            full = os.path.join(root, lp)
            if os.path.exists(full):
                try:
                    os.remove(full)
                    removed.append(lp)
                except Exception as e:
                    skipped.append(lp + " (err:" + str(e) + ")")
    # For dataset groups: keep canonical file in datasets and remove suffixed copies
    # identify base names present
    dataset_paths = [p for p in paths if p.lower().startswith("datasets" + os.sep)]
    if dataset_paths:
        # map basenames without suffix (split at first underscore before extension)
        names = [os.path.basename(p) for p in dataset_paths]
        # find base candidates (exact names without extra suffixes)
        # base is name that equals a known canonical filename (no extra underscore+sfx) e.g. dataset_selected_features_clean_v3.csv
        canonical = None
        for n in names:
            if "_" not in n.split(".csv")[0]:
                canonical = n
                break
        if not canonical:
            # fallback: choose shortest name
            canonical = sorted(names, key=len)[0]
        for p in dataset_paths:
            if os.path.basename(p) == canonical:
                continue
            lp = p.replace("/", os.sep).replace("\\", os.sep)
            if lp.lower().endswith(".exe"):
                skipped.append(lp)
                continue
            full = os.path.join(root, lp)
            if os.path.exists(full):
                try:
                    os.remove(full)
                    removed.append(lp)
                except Exception as e:
                    skipped.append(lp + " (err:" + str(e) + ")")

print("Removed files:")
for r in removed:
    print(" -", r)
print("\nSkipped (not removed):")
for s in skipped:
    print(" -", s)
print("\nSummary: removed=%d skipped=%d" % (len(removed), len(skipped)))
