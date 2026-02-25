from attendance_manager import WFHLeaveManager
import os
from datetime import date

# Initialize manager
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
manager = WFHLeaveManager(BASE_PATH)

# Test parameters
emp_id = 1  # Assuming this is the ID for "Muhammad Ahsan"
start_date = date(2026, 1, 1)
end_date = date(2026, 1, 31)

print(f"Searching for Emp ID: {emp_id} (type: {type(emp_id)})")
print(f"Date Range: {start_date} to {end_date}")

# Check specific file first
test_date = date(2026, 1, 20)
filename = test_date.strftime('%d-%b-%Y').lower() + '.xlsx'
filepath = os.path.join(BASE_PATH, filename)
print(f"Checking file: {filename}")
print(f"File exists: {os.path.exists(filepath)}")

# Run the actual function
records = manager.get_employee_records(emp_id, start_date, end_date)

print(f"\nFound {len(records)} records:")
for r in records:
    print(r)
