import os
import csv

datasets_dir = 'datasets'
files = [f for f in os.listdir(datasets_dir) if f.endswith('.csv')]

results = []
for file_name in files:
    file_path = os.path.join(datasets_dir, file_name)
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if 'churn' not in reader.fieldnames:
                continue
            rows = list(reader)
            churn_count = sum(1 for row in rows if row['churn'] == '1')
            if churn_count == 83:
                results.append((file_name, len(rows), churn_count))
    except Exception as e:
        pass

for res in sorted(results, key=lambda x: x[1]):
    print(f"File: {res[0]}, Total Rows: {res[1]}, Churners: {res[2]}")
