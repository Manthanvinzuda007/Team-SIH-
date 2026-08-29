import os
import pandas as pd

folder = "DataSets/DataSets/updated7_consol"

# Find CSV files
files = [f for f in os.listdir(folder) if f.endswith(".csv")]

print("Number of CSV files:", len(files))
print("Reading:", files[0])

# Read the first CSV
file_path = os.path.join(folder, files[0])
data = pd.read_csv(file_path)

# Show sample
print("\nFirst 5 rows:")
print(data.head())

# Show column names
print("\nColumn names:")
print(data.columns.tolist())