import os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from database_snowflake import SnowflakeDatabase

class WFHLeaveManager:
    def __init__(self, base_path):
        self.base_path = base_path
        self.db = SnowflakeDatabase()

    def get_connection(self):
        return self.db.get_connection()

    def _execute_query(self, query, params=None, fetchone=False, commit=False):
        conn = self.get_connection()
        if not conn:
            return None
        try:
            cur = conn.cursor()
            try:
                if params: cur.execute(query, params)
                else: cur.execute(query)
                
                if commit:
                    conn.commit()
                    return True
                
                if cur.description:
                    columns = [col[0] for col in cur.description]
                    if fetchone:
                        row = cur.fetchone()
                        return dict(zip(columns, row)) if row else None
                    else:
                        rows = cur.fetchall()
                        return [dict(zip(columns, r)) for r in rows]
                return None
            except Exception as e:
                print(f"Snowflake Query Error: {e} - Query: {query}")
                if commit: conn.rollback()
                return None
        finally:
            conn.close()

    def authenticate_user(self, emp_name, password=None, role='employee'):
        try:
            user = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE LOWER(EMP_NAME) = LOWER(%s)", (emp_name,), fetchone=True)
            if not user: return None

            emp_data = {
                'emp_id': user.get('EMP_ID'),
                'emp_name': user.get('EMP_NAME'),
                'emp_team': user.get('EMP_TEAM', ''),
                'is_admin': bool(user.get('IS_ADMIN')),
                'is_manager': bool(user.get('IS_MANAGER')),
                'password': user.get('PASSWORD')
            }
            
            if password and str(emp_data['password']) != str(password):
                return None
            if role == 'admin' and not emp_data['is_admin']:
                return None
            if role == 'manager' and not emp_data['is_manager'] and not emp_data['is_admin']:
                return None
                
            return emp_data
        except Exception as e:
            print(f"Auth Exception: {e}")
            return None

    def change_password(self, emp_id, new_password):
        self._execute_query("UPDATE ADLABS.AHSAN.EMPLOYEES SET PASSWORD = %s WHERE EMP_ID = %s", (new_password, emp_id), commit=True)
        return True

    def _map_employee(self, e):
        """Map Snowflake UPPERCASE column names to Python/Flask expected keys"""
        emp = {}
        # Keep case-insensitive fallback logic for the frontend templates
        for k, v in e.items():
            emp[k.lower()] = v
        # Critical capitalized keys expected by frontend templates
        emp['Total_leaves'] = float(e.get('TOTAL_LEAVES') or 0)
        emp['Remaining_Leaves'] = float(e.get('REMAINING_LEAVES') or 0)
        emp['Leaves_This_Year'] = float(e.get('LEAVES_THIS_YEAR') or 0)
        emp['Leaves_Carried_Forward'] = float(e.get('LEAVES_CARRIED_FORWARD') or 0)
        emp['Contract_Type'] = str(e.get('CONTRACT_TYPE') or '')
        emp['Contract_Start_Date'] = str(e.get('CONTRACT_START_DATE') or '')
        emp['Contract_End_Date'] = str(e.get('CONTRACT_END_DATE') or '')
        emp['Contract_Year_Start'] = str(e.get('CONTRACT_YEAR_START') or '')
        emp['Carried_Forward_Expiry'] = str(e.get('CARRIED_FORWARD_EXPIRY') or '')
        emp['WFH_count'] = float(e.get('WFH_COUNT') or 0) # Just in case
        emp['emp_name'] = e.get('EMP_NAME')
        emp['emp_team'] = e.get('EMP_TEAM')
        
        # Derived fields (calculated on the fly from the database in the new system)
        emp['Leaves'] = emp['Leaves_This_Year']
        emp['Half_Day'] = 0 # Fallback
        
        return emp

    def get_employees(self):
        rows = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES ORDER BY EMP_ID ASC")
        return [self._map_employee(row) for row in rows] if rows else []

    def get_contract_year_window(self, contract_start_date_str, today=None):
        if today is None: today = date.today()
        try:
            contract_start = date.fromisoformat(str(contract_start_date_str).split(' ')[0].split('T')[0])
        except Exception:
            return None, None

        year_start = contract_start
        while True:
            year_end = year_start + relativedelta(years=1) - timedelta(days=1)
            if year_start <= today <= year_end:
                return year_start, year_end
            if year_start > today:
                break
            year_start = year_start + relativedelta(years=1)
        return None, None

    def check_and_rollover_leaves(self, emp_id):
        emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        if not emp: return None
        
        contract_start_str = emp.get('CONTRACT_START_DATE')
        if not contract_start_str: return self._map_employee(emp)
        
        today = date.today()
        year_start, year_end = self.get_contract_year_window(contract_start_str, today)
        if not year_start: return self._map_employee(emp)
        
        year_start_str = year_start.strftime('%Y-%m-%d')
        stored_year_start = emp.get('CONTRACT_YEAR_START')
        if stored_year_start and str(stored_year_start).strip() == year_start_str:
            return self._map_employee(emp)
            
        old_taken = float(emp.get('LEAVES_THIS_YEAR') or 0)
        old_total = float(emp.get('TOTAL_LEAVES') or 0)
        old_carried = float(emp.get('LEAVES_CARRIED_FORWARD') or 0)
        
        old_remaining = max(0, (old_total + old_carried) - old_taken)
        new_carried = old_remaining if (stored_year_start and old_total > 0) else 0
        
        expiry_date = (year_start + relativedelta(months=6)).strftime('%Y-%m-%d')
        new_remaining = old_total + new_carried
        
        self._execute_query(
            """UPDATE ADLABS.AHSAN.EMPLOYEES SET 
                LEAVES_THIS_YEAR = 0, 
                LEAVES_CARRIED_FORWARD = %s, 
                CARRIED_FORWARD_EXPIRY = %s, 
                CONTRACT_YEAR_START = %s, 
                REMAINING_LEAVES = %s 
               WHERE EMP_ID = %s""",
            (new_carried, expiry_date, year_start_str, new_remaining, emp_id), commit=True
        )
        # Fetch updated
        updated_emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        return self._map_employee(updated_emp)

    def check_and_apply_expiry(self, emp_id):
        emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        if not emp: return
        
        expiry_str = emp.get('CARRIED_FORWARD_EXPIRY')
        if not expiry_str: return
        
        try:
            if isinstance(expiry_str, date):
                expiry_date = expiry_str
            else:
                expiry_date = date.fromisoformat(str(expiry_str).split(' ')[0])
        except: return
            
        today = date.today()
        if today >= expiry_date:
            carried = float(emp.get('LEAVES_CARRIED_FORWARD') or 0)
            taken = float(emp.get('LEAVES_THIS_YEAR') or 0)
            
            if carried > 0:
                unused_carried = max(0, carried - taken)
                if unused_carried > 0:
                    new_carried = carried - unused_carried
                    total = float(emp.get('TOTAL_LEAVES') or 0)
                    new_remaining = total + new_carried - taken
                    
                    self._execute_query(
                        "UPDATE ADLABS.AHSAN.EMPLOYEES SET LEAVES_CARRIED_FORWARD = %s, REMAINING_LEAVES = %s, CARRIED_FORWARD_EXPIRY = NULL WHERE EMP_ID = %s",
                        (new_carried, new_remaining, emp_id), commit=True
                    )
            
            self._execute_query("UPDATE ADLABS.AHSAN.EMPLOYEES SET CARRIED_FORWARD_EXPIRY = NULL WHERE EMP_ID = %s", (emp_id,), commit=True)

    def get_leave_balance_info(self, emp_id):
        emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        if not emp: return {}
        
        contract_start_str = emp.get('CONTRACT_START_DATE')
        year_start, year_end = self.get_contract_year_window(str(contract_start_str)) if contract_start_str else (None, None)
        
        total = float(emp.get('TOTAL_LEAVES') or 0)
        carried = float(emp.get('LEAVES_CARRIED_FORWARD') or 0)
        taken = float(emp.get('LEAVES_THIS_YEAR') or 0)
        
        total_available = total + carried
        calculated_remaining = total_available - taken
        
        # Calculate half days by scanning requests dynamically
        counts = self._execute_query(
            "SELECT REQUEST_TYPE, COUNT(*) as CNT FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND STATUS = 'Approved' AND REQUEST_DATE >= %s GROUP BY REQUEST_TYPE",
            (emp_id, year_start.strftime('%Y-%m-%d') if year_start else '1970-01-01')
        )
        half_days = 0
        wfh = 0
        if counts:
            for count_row in counts:
                if count_row.get('REQUEST_TYPE') == 'Half Day': half_days = count_row.get('CNT', 0)
                if count_row.get('REQUEST_TYPE') == 'WFH': wfh = count_row.get('CNT', 0)
        
        return {
            'contract_year_start': year_start.strftime('%d %b %Y') if year_start else 'N/A',
            'contract_year_end': year_end.strftime('%d %b %Y') if year_end else 'N/A',
            'total_leaves': total,
            'carried_forward': carried,
            'total_available': total_available,
            'leaves_taken_this_year': taken,
            'half_days_taken': half_days,
            'remaining_leaves': calculated_remaining,
            'wfh_taken': wfh
        }

    def update_employee_counters(self, emp_id):
        """Full recount and sync of employee balances based on approved requests"""
        try:
            emp_id_int = int(emp_id)
            # 1. Get current employee base data
            emp = self._execute_query("SELECT CARRIED_FORWARD FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id_int,), fetchone=True)
            carried = float(emp.get('CARRIED_FORWARD', 0) or 0)
            base_allowance = 14.0 + carried
            
            # 2. Count Approved Leaves (1.0 each)
            leaves = self._execute_query("SELECT COUNT(*) as cnt FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND STATUS = 'Approved' AND REQUEST_TYPE = 'Leave'", (emp_id_int,), fetchone=True)
            # 3. Count Approved Half Days (0.5 each)
            hds = self._execute_query("SELECT COUNT(*) as cnt FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND STATUS = 'Approved' AND REQUEST_TYPE = 'Half Day'", (emp_id_int,), fetchone=True)
            # 4. Count Approved WFH
            wfhs = self._execute_query("SELECT COUNT(*) as cnt FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND STATUS = 'Approved' AND REQUEST_TYPE = 'WFH'", (emp_id_int,), fetchone=True)
            
            taken_leaves = float(leaves.get('CNT', 0) or 0)
            taken_hds = float(hds.get('CNT', 0) or 0) * 0.5
            total_taken = taken_leaves + taken_hds
            total_wfh = int(wfhs.get('CNT', 0) or 0)
            
            new_remaining = base_allowance - total_taken
            
            # Sync back to EMPLOYEES table
            self._execute_query(
                "UPDATE ADLABS.AHSAN.EMPLOYEES SET REMAINING_LEAVES = %s, LEAVES_THIS_YEAR = %s, WFH_COUNT = %s WHERE EMP_ID = %s",
                (new_remaining, total_taken, total_wfh, emp_id_int), commit=True
            )
            return True
        except Exception as e:
            print(f"[SYNC ERROR] {e}")
            return False

    def refund_employee_counters(self, emp_id, request_type=None):
        # With recount logic, we just sync everything
        return self.update_employee_counters(emp_id)

    def log_approval_action(self, emp_id, emp_name, request_type, request_date, status, manager_name):
        return self.db.log_approval_action(emp_id, emp_name, request_type, request_date, status, manager_name)

    def mark_wfh_leave(self, emp_id, emp_name, emp_team, date, request_type, reason, status='Pending', manager_name=''):
        try: emp_id_int = int(emp_id)
        except: emp_id_int = emp_id
        
        date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        
        # 1. KILL any existing record for this date (Absolute Clean)
        self._execute_query(
            "DELETE FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND TO_CHAR(REQUEST_DATE, 'YYYY-MM-DD') = %s",
            (emp_id_int, date_str), commit=True
        )

        # 2. Insert new
        success = self.db.mark_request(emp_id_int, date_str, request_type, reason, status, manager_name if status == 'Approved' else None)
        
        # 3. Always Recount/Sync after any change
        self.update_employee_counters(emp_id_int)
        
        if status == 'Approved':
            self.log_approval_action(emp_id_int, emp_name, request_type, date_str, 'Approved', manager_name or emp_name)
        
        return True

    def get_notifications(self, filter_date=None, limit=None):
        if filter_date is None: filter_date = date.today()
        query = """
        SELECT r.*, e.EMP_NAME, e.EMP_TEAM 
        FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
        JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
        WHERE r.REQUEST_DATE = %s
        ORDER BY r.SUBMITTED_AT DESC
        """
        rows = self._execute_query(query, (filter_date.strftime('%Y-%m-%d'),))
        
        notifications = []
        if rows:
            for row in rows:
                notifications.append({
                    'date': row.get('REQUEST_DATE').strftime('%d-%b-%Y') if isinstance(row.get('REQUEST_DATE'), date) else row.get('REQUEST_DATE'),
                    'emp_id': row.get('EMP_ID'),
                    'emp_name': row.get('EMP_NAME'),
                    'team': row.get('EMP_TEAM'),
                    'type': row.get('REQUEST_TYPE'),
                    'reason': row.get('REASON'),
                    'timestamp': row.get('SUBMITTED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('SUBMITTED_AT'), 'strftime', None) else str(row.get('SUBMITTED_AT')),
                    'status': row.get('STATUS')
                })
        return notifications

    def get_pending_requests(self, days_back=30, days_forward=365, req_status='Pending'):
        query = """
                SELECT r.*, e.EMP_NAME, e.EMP_TEAM as team
                FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
                JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
                WHERE r.STATUS = 'Pending'
                ORDER BY r.REQUEST_ID DESC
                """
        rows = self._execute_query(query, (req_status,))
        
        requests_list = []
        if rows:
            for row in rows:
                req_date = row.get('REQUEST_DATE')
                req_date_obj = req_date if isinstance(req_date, date) else datetime.strptime(str(req_date).split(' ')[0], '%Y-%m-%d').date()
                requests_list.append({
                    'date': req_date_obj.strftime('%Y-%m-%d'),
                    'display_date': req_date_obj.strftime('%d-%b-%Y'),
                    'emp_id': row.get('EMP_ID'),
                    'emp_name': row.get('EMP_NAME'),
                    'team': row.get('EMP_TEAM'),
                    'type': row.get('REQUEST_TYPE'),
                    'reason': row.get('REASON'),
                    'timestamp': row.get('SUBMITTED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('SUBMITTED_AT'), 'strftime', None) else str(row.get('SUBMITTED_AT')),
                    'status': row.get('STATUS')
                })
        return requests_list

    def update_request_status(self, request_date_str, emp_id, request_type, timestamp, new_status, manager_name):
        # We need to find the specific request. Using EMP_ID and SUBMITTED_AT or DATE is best.
        # SQLite SUBMITTED_AT formatting might differ from Snowflake string format. 
        # Safest to just match EMP_ID, DATE, and TYPE which is very likely unique.
        success = self._execute_query(
            "UPDATE ADLABS.AHSAN.ATTENDANCE_REQUESTS SET STATUS = %s, APPROVED_BY = %s WHERE EMP_ID = %s AND REQUEST_DATE = %s AND REQUEST_TYPE = %s AND STATUS = 'Pending'",
            (new_status, manager_name, emp_id, request_date_str, request_type), commit=True
        )
        if success:
            if new_status == 'Approved':
                self.update_employee_counters(emp_id, request_type)
            # Find emp name
            emp_name = self._execute_query("SELECT EMP_NAME FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
            self.log_approval_action(emp_id, emp_name.get('EMP_NAME') if emp_name else str(emp_id), request_type, request_date_str, new_status, manager_name)
            return True
        raise Exception("Could not find the specific request to update.")

    def cancel_request(self, request_date_str, emp_id, timestamp, cancelled_by):
        # Find current status
        # Note: If there are multiple requests on same day, this picks chronologically latest or limits 1. Let's rely on date + id + timestamp if available. 
        # For snowflake matching exact timestamps can be flaky via string. Using DATE + ID
        req = self._execute_query(
            "SELECT STATUS, REQUEST_TYPE FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND REQUEST_DATE = %s AND STATUS IN ('Approved', 'Pending') LIMIT 1",
            (emp_id, request_date_str), fetchone=True
        )
        if not req:
            raise Exception("Could not find the specific request to cancel.")
            
        current_status = req.get('STATUS')
        request_type = req.get('REQUEST_TYPE')
        
        if current_status == 'Approved':
            self.refund_employee_counters(emp_id, request_type)
            
        self._execute_query(
            "UPDATE ADLABS.AHSAN.ATTENDANCE_REQUESTS SET STATUS = 'Cancelled', APPROVED_BY = %s WHERE EMP_ID = %s AND REQUEST_DATE = %s",
            (cancelled_by, emp_id, request_date_str), commit=True
        )
        return True

    def get_approval_log(self, limit=50):
        rows = self._execute_query("SELECT * FROM ADLABS.AHSAN.APPROVAL_LOGS ORDER BY ACTIONED_AT DESC LIMIT %s", (limit,))
        logs = []
        if rows:
            for row in rows:
                logs.append({
                    'emp_id': row.get('EMP_ID'),
                    'emp_name': row.get('EMP_NAME'),
                    'request_type': row.get('REQUEST_TYPE'),
                    'request_date': row.get('REQUEST_DATE').strftime('%Y-%m-%d') if getattr(row.get('REQUEST_DATE'), 'strftime', None) else str(row.get('REQUEST_DATE')),
                    'status': row.get('STATUS'),
                    'manager_name': row.get('MANAGER_NAME'),
                    'actioned_at': row.get('ACTIONED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('ACTIONED_AT'), 'strftime', None) else str(row.get('ACTIONED_AT'))
                })
        return logs

    def get_employee_records(self, emp_id, start_date, end_date):
        rows = self._execute_query(
            "SELECT * FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND REQUEST_DATE >= %s AND REQUEST_DATE <= %s ORDER BY REQUEST_DATE ASC",
            (emp_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        )
        records = []
        if rows:
            for row in rows:
                req_date = row.get('REQUEST_DATE')
                req_date_obj = req_date if isinstance(req_date, date) else datetime.strptime(str(req_date).split(' ')[0], '%Y-%m-%d').date()
                
                records.append({
                    'date': req_date_obj.strftime('%d-%b-%Y'),
                    'raw_date': req_date_obj.strftime('%Y-%m-%d'),
                    'type': row.get('REQUEST_TYPE'),
                    'reason': row.get('REASON'),
                    'timestamp': row.get('SUBMITTED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('SUBMITTED_AT'), 'strftime', None) else str(row.get('SUBMITTED_AT')),
                    'status': row.get('STATUS')
                })
        return records

    def add_employee(self, emp_name, emp_team, is_admin, is_manager, contract_type, contract_start_date, contract_end_date, total_leaves, password='SecurePass2026!'):
        """Add new employee to Snowflake"""
        max_id_row = self._execute_query("SELECT MAX(EMP_ID) as M FROM ADLABS.AHSAN.EMPLOYEES", fetchone=True)
        new_id = (max_id_row.get('M') or 0) + 1 if max_id_row else 1
        
        year_start = None
        if contract_start_date:
            try:
                ys, _ = self.get_contract_year_window(contract_start_date)
                year_start = ys.strftime('%Y-%m-%d') if ys else None
            except: pass
            
        sql = """INSERT INTO ADLABS.AHSAN.EMPLOYEES (
            EMP_ID, EMP_NAME, EMP_TEAM, PASSWORD, IS_ADMIN, IS_MANAGER, 
            CONTRACT_START_DATE, TOTAL_LEAVES, REMAINING_LEAVES, LEAVES_THIS_YEAR, 
            LEAVES_CARRIED_FORWARD, PHONE, CONTRACT_TYPE, CONTRACT_END_DATE, CONTRACT_YEAR_START
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        
        self._execute_query(sql, (
            new_id, emp_name, emp_team, password, is_admin, is_manager, 
            contract_start_date, total_leaves, total_leaves, 0, 
            0, '', contract_type, contract_end_date, year_start
        ), commit=True)
        return new_id

    def update_employee(self, emp_id, emp_name, emp_team, is_admin, is_manager, contract_type, contract_start_date, contract_end_date, total_leaves, carried_forward=None, phone=None):
        emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        if not emp: raise Exception("Employee not found")
        
        # Trigger recalculation of contract year if contract start date changed
        old_csd = str(emp.get('CONTRACT_START_DATE') or '').strip()
        new_csd = str(contract_start_date).strip() if contract_start_date else ''
        year_start_nullify = ""
        if new_csd != old_csd:
            year_start_nullify = ", CONTRACT_YEAR_START = NULL"
            
        old_taken = float(emp.get('LEAVES_THIS_YEAR') or 0)
        curr_carried = float(emp.get('LEAVES_CARRIED_FORWARD') or 0)
        if carried_forward is not None:
             curr_carried = float(carried_forward)
             
        new_rem = (float(total_leaves) + curr_carried) - old_taken
        
        sql = f"""UPDATE ADLABS.AHSAN.EMPLOYEES SET 
            EMP_NAME = %s, EMP_TEAM = %s, IS_ADMIN = %s, IS_MANAGER = %s,
            CONTRACT_TYPE = %s, CONTRACT_START_DATE = %s, CONTRACT_END_DATE = %s,
            TOTAL_LEAVES = %s, LEAVES_CARRIED_FORWARD = %s, REMAINING_LEAVES = %s,
            PHONE = COALESCE(%s, PHONE)
            {year_start_nullify}
            WHERE EMP_ID = %s
        """
        self._execute_query(sql, (
            emp_name, emp_team, is_admin, is_manager, contract_type, contract_start_date, contract_end_date,
            total_leaves, curr_carried, new_rem, phone, emp_id
        ), commit=True)
        return True

    def delete_employee(self, emp_id):
        self._execute_query("DELETE FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), commit=True)
        return True

    def get_manager_for_team(self, team_name: str) -> dict:
        mgr = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_TEAM = %s AND IS_MANAGER = TRUE LIMIT 1", (team_name,), fetchone=True)
        if mgr: return self._map_employee(mgr)
        
        admin = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE IS_ADMIN = TRUE LIMIT 1", fetchone=True)
        if admin: return self._map_employee(admin)
        
        return {}
        
    def get_employee_phone(self, emp_id) -> str:
        emp = self._execute_query("SELECT PHONE FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        return str(emp.get('PHONE', '')) if emp else ''

    def get_all_managers(self) -> list:
        rows = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE IS_MANAGER = TRUE")
        return [self._map_employee(r) for r in rows] if rows else []

    def get_daily_attendance_summary(self, summary_date):
        teams = {}
        all_emps = self.get_employees()
        
        # Initialize
        for e in all_emps:
            team = e.get('emp_team', 'Unknown')
            if team not in teams:
                teams[team] = {'wfh': [], 'leave': [], 'half_day': [], 'no_request': []}
                
        # Get requests for today
        reqs = self._execute_query("SELECT EMP_ID, REQUEST_TYPE FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE REQUEST_DATE = %s AND STATUS IN ('Approved', 'Pending')", (summary_date.strftime('%Y-%m-%d'),))
        filed_by_emp = {}
        if reqs:
            for r in reqs:
                filed_by_emp[str(r.get('EMP_ID'))] = r.get('REQUEST_TYPE')
                
        for e in all_emps:
            team = e.get('emp_team', 'Unknown')
            emp_id_str = str(e.get('emp_id'))
            emp_name = e.get('emp_name')
            is_mgr_adm = e.get('is_manager', 0) or e.get('is_admin', 0)
            
            if emp_id_str in filed_by_emp:
                rtype = filed_by_emp[emp_id_str]
                if rtype == 'WFH': teams[team]['wfh'].append(emp_name)
                elif rtype == 'Leave': teams[team]['leave'].append(emp_name)
                elif rtype == 'Half Day': teams[team]['half_day'].append(emp_name)
            elif summary_date.weekday() < 5 and not is_mgr_adm:
                teams[team]['no_request'].append(emp_name)
                
        return teams
