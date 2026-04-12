import pandas as pd
import os

excel_file = 'Emp_data.xlsx'

if not os.path.exists(excel_file):
    print(f"Error: {excel_file} not found.")
else:
    df = pd.read_excel(excel_file)
    
    # Manager data from user
    managers_data = [
        {'id': 5, 'name': 'Hafiz Zohaib', 'phone': '03365111740', 'team': 'Overstock'},
        {'id': 9, 'name': 'Sajeel Fasihi', 'phone': '03245494440', 'team': 'Poppi'},
        {'id': 11, 'name': 'Hatif Javed', 'phone': '03365404410', 'team': 'LHM'}
    ]
    
    # Ensure phone column is string type
    if 'phone' not in df.columns:
        df['phone'] = ''
    df['phone'] = df['phone'].astype(str)

    for mgr in managers_data:
        mask = df['emp_id'] == mgr['id']
        if any(mask):
            df.loc[mask, 'emp_name'] = mgr['name']
            df.loc[mask, 'phone'] = mgr['phone']
            df.loc[mask, 'emp_team'] = mgr['team']
            df.loc[mask, 'is_manager'] = 1
            print(f"Updated {mgr['name']} (ID {mgr['id']})")
        else:
            print(f"Warning: Manager ID {mgr['id']} not found.")

    # Save it back
    df.to_excel(excel_file, index=False)
    print("Excel updated successfully.")
