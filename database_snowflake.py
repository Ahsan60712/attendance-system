
import snowflake.connector
import os
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

# --- SNOWFLAKE CONFIG ---
# These should ideally come from environment variables
SNOW_ACCOUNT  = 'wxlwerb-rg07665'
SNOW_USER     = 'MUHAMMAD.AHSAN'     
SNOW_PASSWORD = 'Ahsan123$' 
SNOW_DATABASE = 'ADLABS'
SNOW_SCHEMA   = 'AHSAN'
SNOW_WH       = 'ADLABS_WH'
SNOW_ROLE     = 'ADLABS_ROLE'

class SnowflakeDatabase:
    def __init__(self):
        self._conn = None

    def get_connection(self):
        # Reuse existing connection if it's still alive
        if self._conn is not None:
            try:
                if not getattr(self._conn, 'is_closed', False):
                    return self._conn
            except:
                pass
            self._conn = None
        
        try:
            self._conn = snowflake.connector.connect(
                user=SNOW_USER,
                password=SNOW_PASSWORD,
                account=SNOW_ACCOUNT,
                warehouse=SNOW_WH,
                database=SNOW_DATABASE,
                schema=SNOW_SCHEMA,
                role=SNOW_ROLE
            )
            return self._conn
        except Exception as e:
            logger.error(f"Snowflake Connection Error: {e}")
            return None

    def get_employee(self, emp_id):
        """Fetch employee details by ID"""
        conn = self.get_connection()
        if not conn: return None
        try:
            cur = conn.cursor(snowflake.connector.DictCursor)
            cur.execute("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,))
            result = cur.fetchone()
            cur.close()
            return result
        except Exception as e:
            logger.error(f"Error getting employee: {e}")
            return None

    def get_team_manager(self, team_name):
        """Find the manager for a specific team"""
        conn = self.get_connection()
        if not conn: return None
        try:
            cur = conn.cursor(snowflake.connector.DictCursor)
            cur.execute("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_TEAM = %s AND IS_MANAGER = TRUE LIMIT 1", (team_name,))
            result = cur.fetchone()
            cur.close()
            return result
        except Exception as e:
            logger.error(f"Error getting team manager: {e}")
            return None

    def get_pending_requests(self, manager_team=None):
        """Fetch pending requests (filtered by team if manager)"""
        conn = self.get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(snowflake.connector.DictCursor)
            if manager_team:
                sql = """
                SELECT r.*, e.EMP_NAME, e.EMP_TEAM 
                FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
                JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
                WHERE r.STATUS = 'Pending' AND e.EMP_TEAM = %s
                ORDER BY r.REQUEST_DATE DESC
                """
                cur.execute(sql, (manager_team,))
            else:
                sql = """
                SELECT r.*, e.EMP_NAME, e.EMP_TEAM 
                FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
                JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
                WHERE r.STATUS = 'Pending'
                ORDER BY r.REQUEST_DATE DESC
                """
                cur.execute(sql)
            results = cur.fetchall()
            cur.close()
            return results
        except Exception as e:
            logger.error(f"Error getting pending requests: {e}")
            return []

    def mark_request(self, emp_id, req_date, req_type, reason, status='Pending', approved_by=None):
        """Create a new attendance request"""
        conn = self.get_connection()
        if not conn: return False
        try:
            cur = conn.cursor()
            sql = """
            INSERT INTO ADLABS.AHSAN.ATTENDANCE_REQUESTS 
            (EMP_ID, REQUEST_DATE, REQUEST_TYPE, REASON, STATUS, APPROVED_BY)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (emp_id, req_date, req_type, reason, status, approved_by))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Error marking request: {e}")
            return False

    def update_request_status(self, request_id, status, manager_name):
        """Approve or Reject a request"""
        conn = self.get_connection()
        if not conn: return False
        try:
            cur = conn.cursor()
            sql = "UPDATE ADLABS.AHSAN.ATTENDANCE_REQUESTS SET STATUS = %s, APPROVED_BY = %s WHERE REQUEST_ID = %s"
            cur.execute(sql, (status, manager_name, request_id))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Error updating request status: {e}")
            return False

    def update_employee_counters(self, emp_id, request_type):
        """Increment WFH count or decrement leaves in Snowflake"""
        conn = self.get_connection()
        if not conn: return False
        try:
            cur = conn.cursor()
            if request_type == 'WFH':
                cur.execute("UPDATE ADLABS.AHSAN.EMPLOYEES SET WFH_COUNT = COALESCE(WFH_COUNT, 0) + 1 WHERE EMP_ID = %s", (emp_id,))
            elif request_type == 'Leave':
                cur.execute("UPDATE ADLABS.AHSAN.EMPLOYEES SET REMAINING_LEAVES = REMAINING_LEAVES - 1, LEAVES_THIS_YEAR = LEAVES_THIS_YEAR + 1 WHERE EMP_ID = %s", (emp_id,))
            elif request_type == 'Half Day':
                cur.execute("UPDATE ADLABS.AHSAN.EMPLOYEES SET REMAINING_LEAVES = REMAINING_LEAVES - 0.5, LEAVES_THIS_YEAR = LEAVES_THIS_YEAR + 0.5 WHERE EMP_ID = %s", (emp_id,))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Error updating employee counters: {e}")
            return False

    def log_approval_action(self, emp_id, emp_name, request_type, request_date, status, manager_name):
        """Log approval actions for auditing"""
        conn = self.get_connection()
        if not conn: return False
        try:
            cur = conn.cursor()
            sql = """
            INSERT INTO ADLABS.AHSAN.APPROVAL_LOGS (EMP_ID, EMP_NAME, REQUEST_TYPE, REQUEST_DATE, STATUS, MANAGER_NAME)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (emp_id, emp_name, request_type, request_date, status, manager_name))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Error logging approval action: {e}")
            return False
