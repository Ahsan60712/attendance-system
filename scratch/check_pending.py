from attendance_manager import WFHLeaveManager
import os

def check_data():
    manager = WFHLeaveManager(".")
    
    print("--- 1. Checking Hafiz's Info (ID 5) ---")
    emp = manager._execute_query("SELECT EMP_ID, EMP_NAME, EMP_TEAM, IS_MANAGER FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = 5", fetchone=True)
    print(f"Hafiz Zohaib Data: {emp}")

    print("\n--- 2. Checking ALL Pending Requests ---")
    reqs = manager._execute_query("""
        SELECT r.EMP_ID, e.EMP_NAME, e.EMP_TEAM, r.STATUS 
        FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
        JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
        WHERE r.STATUS = 'Pending'
    """)
    if not reqs:
        print("NO PENDING REQUESTS FOUND IN DATABASE AT ALL!")
    else:
        for r in reqs:
            print(f"Request from: {r['EMP_NAME']}, Team: '{r['EMP_TEAM']}', Status: {r['STATUS']}")

if __name__ == "__main__":
    check_data()
