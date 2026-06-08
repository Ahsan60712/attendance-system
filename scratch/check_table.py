
from database_snowflake import SnowflakeDatabase

db = SnowflakeDatabase()
conn = db.get_connection()
if conn:
    cur = conn.cursor()
    cur.execute("DESCRIBE TABLE ADLABS.AHSAN.ATTENDANCE_REQUESTS")
    for col in cur.fetchall():
        print(col)
    conn.close()
else:
    print("Failed to connect")
