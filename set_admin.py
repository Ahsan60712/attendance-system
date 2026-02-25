import pandas as pd

try:
    # Read the existing Excel file
    df = pd.read_excel('Emp_data.xlsx')

    # Target name found in the file
    target_name = "Najam "
    
    # Check if target exists
    matches = df[df['emp_name'] == target_name]
    
    if matches.empty:
        print(f"Error: Could not find employee '{target_name}' in Emp_data.xlsx")
        print("Available employees:")
        print(df['emp_name'].tolist())
    else:
        # Reset all to 0 first
        df['is_admin'] = 0
        
        # Set Najam to 1
        mask = df['emp_name'] == target_name
        df.loc[mask, 'is_admin'] = 1
        
        # Save back to Excel
        df.to_excel('Emp_data.xlsx', index=False)
        print(f"Successfully updated admin to: '{target_name}'")
        
        # Verify
        admin_row = df[df['is_admin'] == 1]
        print(f"Current Admin(s): {admin_row['emp_name'].tolist()}")

except Exception as e:
    print(f"Error updating file: {e}")
