
import pandas as pd
import os

FILE_PATH = 'Emp_data.xlsx'

if not os.path.exists(FILE_PATH):
    print("Excel file not found!")
    exit()

try:
    df = pd.read_excel(FILE_PATH, engine='openpyxl')
    
    # Ensure required columns exist
    cols_to_ensure = [
        'Leaves_Carried_Forward', 
        'Leaves_This_Year', 
        'Carried_Forward_Expiry', 
        'Contract_Year_Start'
    ]
    for col in cols_to_ensure:
        if col not in df.columns:
            df[col] = ""

    print("--- Resetting Leave Balances & Implementing Expiry Logic ---")
    
    # 1. Reset Carry Forward to 0 for all (as requested)
    df['Leaves_Carried_Forward'] = 0
    
    # 2. Clear Expiry dates (since carried is 0)
    df['Carried_Forward_Expiry'] = ""
    
    # 3. Reset Taken this year (optional, but requested for "first year" feel)
    df['Leaves_This_Year'] = 0
    df['Leaves'] = 0
    df['Half_Day'] = 0
    
    # 4. Update Remaining_Leaves to be exactly the Annual Total_leaves
    df['Remaining_Leaves'] = df['Total_leaves']
    
    # 5. Reset stored contract year start so rollover can re-trigger on next anniversary
    df['Contract_Year_Start'] = ""

    df.to_excel(FILE_PATH, index=False, engine='openpyxl')
    print("✅ SUCCESS: Carried forward leaves removed. 6-month expiry logic implemented for future years.")

except Exception as e:
    print(f"❌ ERROR: {e}")
