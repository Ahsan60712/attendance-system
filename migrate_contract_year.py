"""
One-time migration script:
1. Adds Leaves_This_Year, Leaves_Carried_Forward, Contract_Year_Start columns
2. Seeds sample Contract_Start_Date for employees who don't have one
   (uses real data feel - spread across months)
3. Initialises Leaves_This_Year = existing Leaves count (so history is preserved)
"""
import pandas as pd
import os

BASE = os.path.dirname(os.path.abspath(__file__))
filepath = os.path.join(BASE, 'Emp_data.xlsx')

df = pd.read_excel(filepath, engine='openpyxl', dtype=object)  # read all as object to avoid dtype fights

# Ensure new columns exist
for col in ['Leaves_This_Year', 'Leaves_Carried_Forward', 'Contract_Year_Start']:
    if col not in df.columns:
        df[col] = ''

# Sample contract start dates for existing employees (spread across the year)
sample_dates = {
    1: '2025-01-15',
    2: '2025-03-01',
    3: '2025-06-15',
    4: '2025-09-01',
    5: '2025-02-20',
    6: '2025-04-10',
    7: '2025-07-01',
    8: '2025-11-15',
    9: '2025-08-01',
    10: '2025-05-12',
    11: '2025-10-20',
    12: '2025-12-01',
    13: '2025-01-25',
    14: '2025-03-30',
    15: '2025-06-01',
    16: '2025-09-15',
    17: '2025-02-01',
    18: '2025-07-20',
}

for i, row in df.iterrows():
    emp_id = int(row['emp_id']) if str(row['emp_id']).replace('.','').isdigit() else None
    if emp_id is None:
        continue

    # Set contract start date if not already set
    existing_csd = str(row.get('Contract_Start_Date', '')).strip()
    if not existing_csd or existing_csd in ('nan', 'None', ''):
        if emp_id in sample_dates:
            df.at[i, 'Contract_Start_Date'] = sample_dates[emp_id]

    # Initialise Leaves_This_Year from existing Leaves value (preserve history)
    leaves_val = str(row.get('Leaves', '0')).strip()
    if leaves_val in ('', 'nan', 'None'):
        leaves_val = '0'
    existing_lty = str(df.at[i, 'Leaves_This_Year']).strip()
    if not existing_lty or existing_lty in ('nan', 'None', '', '0'):
        df.at[i, 'Leaves_This_Year'] = leaves_val

    # Initialise Leaves_Carried_Forward to 0 if blank
    existing_lcf = str(df.at[i, 'Leaves_Carried_Forward']).strip()
    if not existing_lcf or existing_lcf in ('nan', 'None', ''):
        df.at[i, 'Leaves_Carried_Forward'] = '0'

df.to_excel(filepath, index=False, engine='openpyxl')
print('Migration complete. Updated columns:')
print(df[['emp_id', 'emp_name', 'Contract_Start_Date', 'Leaves', 'Leaves_This_Year', 'Leaves_Carried_Forward', 'Remaining_Leaves']].to_string())
