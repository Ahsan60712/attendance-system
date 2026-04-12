from attendance_manager import WFHLeaveManager
import os

mgr = WFHLeaveManager(os.path.dirname(os.path.abspath(__file__)))

print("=== Leave Balance Info for all employees ===")
employees = mgr.get_employees()
for e in employees:
    info = mgr.get_leave_balance_info(int(e['emp_id']))
    print(
        f"  [{e['emp_id']}] {e['emp_name']}: "
        f"year={info.get('contract_year_start')} to {info.get('contract_year_end')} | "
        f"entitlement={info.get('total_leaves')} "
        f"+ carried={info.get('carried_forward')} "
        f"= available={info.get('total_available')} | "
        f"taken={info.get('leaves_taken_this_year')} | "
        f"remaining={info.get('remaining_leaves')}"
    )
