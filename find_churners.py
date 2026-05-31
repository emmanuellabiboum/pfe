import os
import csv

datasets_dir = 'datasets'
files = [f for f in os.listdir(datasets_dir) if f.endswith('.csv')]

for file_name in files:
    file_path = os.path.join(datasets_dir, file_name)
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if 'churn' not in reader.fieldnames:
                continue
            churn_count = sum(1 for row in reader if row['churn'] == '1')
            if churn_count == 83:
                print(f"MATCH FOUND: {file_name} has {churn_count} churners")
            else:
                # print(f"{file_name}: {churn_count} churners")
                pass
    except Exception as e:
        # print(f"Error reading {file_name}: {e}")
        pass
