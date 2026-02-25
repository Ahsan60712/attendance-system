import pandas as pd
import os

try:
    if os.path.exists('Emp_data.xlsx'):
        df = pd.read_excel('Emp_data.xlsx')
        print("Columns:", df.columns.tolist())
        print("First row:", df.iloc[0].to_dict() if not df.empty else "Empty")
    else:
        print("Emp_data.xlsx not found")
except Exception as e:
    print(e)
