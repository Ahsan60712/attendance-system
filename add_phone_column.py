"""
One-time migration script: adds a 'phone' column to Emp_data.xlsx
Run once from the project root:  python add_phone_column.py

After running, open Emp_data.xlsx and fill in each manager's WhatsApp
phone number in the 'phone' column using international format, e.g.:
  +923001234567  (Pakistan)
  +447911123456  (UK)
"""

import os
import pandas as pd

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH = os.path.join(BASE_PATH, 'Emp_data.xlsx')

df = pd.read_excel(EXCEL_PATH, engine='openpyxl')

if 'phone' in df.columns:
    print("✅ 'phone' column already exists — nothing to do.")
else:
    df['phone'] = ''
    df.to_excel(EXCEL_PATH, index=False, engine='openpyxl')
    print("✅ 'phone' column added to Emp_data.xlsx")
    print("   Open Emp_data.xlsx and enter each manager's WhatsApp number.")
    print("   Format: +923001234567  (include country code, no spaces)")
