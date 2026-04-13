
import pandas as pd
import os

FILE_PATH = 'Emp_data.xlsx'

if not os.path.exists(FILE_PATH):
    print("Excel file not found!")
    exit()

try:
    df = pd.read_excel(FILE_PATH, engine='openpyxl')
    
    # Replace spaces with underscores in emp_name column
    if 'emp_name' in df.columns:
        old_names = df['emp_name'].tolist()
        df['emp_name'] = df['emp_name'].str.replace(' ', '_', regex=False)
        new_names = df['emp_name'].tolist()
        
        for old, new in zip(old_names, new_names):
            if old != new:
                print(f"Renamed: {old} -> {new}")
        
        df.to_excel(FILE_PATH, index=False, engine='openpyxl')
        print(f"✅ SUCCESS: All employee names updated with underscores.")
    else:
        print(f"⚠️ ERROR: Column 'emp_name' not found.")

except Exception as e:
    print(f"❌ ERROR: {e}")
