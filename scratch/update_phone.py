
import pandas as pd
import os

FILE_PATH = 'Emp_data.xlsx'
OLD_NAME = 'Hafiz Zohaib'
NEW_PHONE = '03365111740'

if not os.path.exists(FILE_PATH):
    print("Excel file not found!")
    exit()

try:
    df = pd.read_excel(FILE_PATH, engine='openpyxl')
    
    # Force phone column to string type to avoid float errors
    if 'phone' in df.columns:
        df['phone'] = df['phone'].astype(str)
    else:
        df['phone'] = ""
        
    mask = df['emp_name'].str.lower() == OLD_NAME.lower()
    if mask.any():
        df.loc[mask, 'phone'] = NEW_PHONE
        df.to_excel(FILE_PATH, index=False, engine='openpyxl')
        print(f"✅ SUCCESS: Updated {OLD_NAME}'s phone number to {NEW_PHONE} in Excel.")
    else:
        print(f"⚠️ WARNING: Employee '{OLD_NAME}' not found in Excel.")

except Exception as e:
    print(f"❌ ERROR: {e}")
