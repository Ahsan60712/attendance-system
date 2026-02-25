from attendance_manager import WFHLeaveManager
import os
from datetime import date

# Initialize manager
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
manager = WFHLeaveManager(BASE_PATH)

# Test Date: Jan 20, 2026 (We know this file exists from previous turn)
test_date = date(2026, 1, 20)
print(f"Testing notifications for date: {test_date}")

notifications = manager.get_notifications(filter_date=test_date)

print(f"Found {len(notifications)} notifications:")
for n in notifications:
    print(n)

# Test Date: Today (likely empty if no one marked today)
print(f"\nTesting notifications for today: {date.today()}")
notifications_today = manager.get_notifications(filter_date=date.today())
print(f"Found {len(notifications_today)} notifications:")
