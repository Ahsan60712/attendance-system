
import pandas as pd
import os

FILE_PATH = 'Emp_data.xlsx'

if not os.path.exists(FILE_PATH):
    print("Excel file not found!")
    exit()

try:
    df = pd.read_excel(FILE_PATH, engine='openpyxl')
    
    # 1. Ensure required columns exist
    if 'Leaves_Carried_Forward' not in df.columns:
        df['Leaves_Carried_Forward'] = 0
    if 'Leaves_This_Year' not in df.columns:
        df['Leaves_This_Year'] = 0

    print("--- Resetting Leave Balances for First Year ---")
    
    # 2. Reset Carry Forward to 0
    df['Leaves_Carried_Forward'] = 0
    
    # 3. Reset Taken this year to 0 (optional based on whether they want to clear history)
    # The user said "is year ki to 14 hi leaves hain", implying fresh start.
    df['Leaves_This_Year'] = 0
    df['Leaves'] = 0
    df['Half_Day'] = 0
    
    # 4. Update Remaining_Leaves to be exactly the Annual Total_leaves
    # (Since carried is now 0 and taken is now 0)
    df['Remaining_Leaves'] = df['Total_leaves']
    
    # 5. Clear stored contract year start so it picks up the join date cycle fresh
    if 'Contract_Year_Start' in df.columns:
        df['Contract_Year_Start'] = ""

    df.to_excel(FILE_PATH, index=False, engine='openpyxl')
    print("✅ SUCCESS: All employees reset to 14 leaves (0 carried forward).")

except Exception as e:
    print(f"❌ ERROR: {e}")
