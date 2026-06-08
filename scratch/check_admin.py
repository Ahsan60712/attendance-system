import sys
sys.path.insert(0, '.')
from database_snowflake import SnowflakeDatabase

db = SnowflakeDatabase()
conn = db.get_connection()
if conn:
    cur = conn.cursor()
    cur.execute("SELECT EMP_ID, EMP_NAME, IS_ADMIN, IS_MANAGER FROM ADLABS.AHSAN.EMPLOYEES WHERE IS_ADMIN = TRUE")
    for row in cur.fetchall():
        print(f"ID: {row[0]}, Name: {row[1]}, Admin: {row[2]}, Manager: {row[3]}")
    
    print("\n--- All Pending Requests ---")
    cur.execute("SELECT r.REQUEST_ID, r.EMP_ID, e.EMP_NAME, r.REQUEST_TYPE, r.REQUEST_DATE, r.STATUS FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID WHERE r.STATUS = 'Pending' ORDER BY r.SUBMITTED_AT DESC")
    for row in cur.fetchall():
        print(f"  ReqID: {row[0]}, EmpID: {row[1]}, Name: {row[2]}, Type: {row[3]}, Date: {row[4]}, Status: {row[5]}")
    
    print("\n--- Recent Requests (last 10) ---")
    cur.execute("SELECT r.REQUEST_ID, r.EMP_ID, e.EMP_NAME, r.REQUEST_TYPE, r.REQUEST_DATE, r.STATUS, r.SUBMITTED_AT FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID ORDER BY r.SUBMITTED_AT DESC LIMIT 10")
    for row in cur.fetchall():
        print(f"  ReqID: {row[0]}, EmpID: {row[1]}, Name: {row[2]}, Type: {row[3]}, Date: {row[4]}, Status: {row[5]}, At: {row[6]}")
    
    conn.close()
else:
    print("Connection failed!")
