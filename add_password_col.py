import pandas as pd
import os

try:
    # Read the existing Excel file
    if not os.path.exists('Emp_data.xlsx'):
        print("Error: Emp_data.xlsx not found.")
    else:
        df = pd.read_excel('Emp_data.xlsx')

        # Add password column if it doesn't exist
        if 'password' not in df.columns:
            df['password'] = '123456'  # Default password
            print("Added 'password' column with default value '123456'")
        else:
            print("'password' column already exists")

        # Save back to Excel
        df.to_excel('Emp_data.xlsx', index=False)
        print("Successfully updated Emp_data.xlsx")
        print(df[['emp_name', 'password', 'is_admin']].head())

except Exception as e:
    print(f"Error updating file: {e}")
