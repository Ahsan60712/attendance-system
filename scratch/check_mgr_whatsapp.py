
import pandas as pd
import os

# Path to the data file
excel_path = r'c:\Users\ahsan\Desktop\Attandance management system\Emp_data.xlsx'

if os.path.exists(excel_path):
    df = pd.read_excel(excel_path)
    # Check managers
    managers = df[df['is_manager'] == 1]
    print("--- Current Managers in System ---")
    print(managers[['emp_id', 'emp_name', 'emp_team', 'phone']])
else:
    print("Excel file not found!")
