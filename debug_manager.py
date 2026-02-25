from attendance_manager import WFHLeaveManager
import os
from datetime import date

base_path = os.getcwd()
manager = WFHLeaveManager(base_path)

print("--- Data Check ---")
try:
    emps = manager.get_employees()
    print(f"Total employees: {len(emps)}")
    if emps:
        print(f"Sample employee: {emps[0]['emp_name']} (ID: {emps[0]['emp_id']})")
except Exception as e:
    print(f"Error reading employees: {e}")

print("\n--- Notification Check ---")
try:
    notifs = manager.get_notifications(date.today())
    print(f"Notifications today: {len(notifs)}")
except Exception as e:
    print(f"Error getting notifications: {e}")

print("\n--- Filepath Check ---")
try:
    path = manager.get_daily_filepath(date.today())
    print(f"Target path: {path}")
except Exception as e:
    print(f"Error getting filepath: {e}")
