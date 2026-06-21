import os
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

from database_snowflake import SnowflakeDatabase

def normalize_request_type(rtype):
    if not rtype:
        return ''
    rtype_upper = str(rtype).strip().upper()
    if rtype_upper in ('LEAVE', 'LEAVES'):
        return 'Leave'
    elif rtype_upper in ('HALF_DAY', 'HALF DAY', 'HALF-DAY'):
        return 'Half Day'
    elif rtype_upper == 'WFH':
        return 'WFH'
    return str(rtype).strip()

def normalize_status(status):
    if not status:
        return ''
    status_upper = str(status).strip().upper()
    if status_upper == 'APPROVED':
        return 'Approved'
    elif status_upper == 'REJECTED':
        return 'Rejected'
    elif status_upper == 'PENDING':
        return 'Pending'
    elif status_upper == 'CANCELLED':
        return 'Cancelled'
    return str(status).strip()

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
            if params: cur.execute(query, params)
            else: cur.execute(query)
            
            if commit:
                conn.commit()
                # Fix: Blind return True ki jagah actual affected rows check karein ga taake 0 rows par success trigger na ho
                return cur.rowcount if (cur.rowcount is not None and cur.rowcount > 0) else False
            
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
                'is_ceo': bool(user.get('IS_CEO')),
                'password': user.get('PASSWORD')
            }
            
            if password and str(emp_data['password']) != str(password):
                return None
            # Admin login accepts both IS_ADMIN users (Sajeel) and IS_CEO users (Najm)
            if role == 'admin' and not emp_data['is_admin'] and not emp_data['is_ceo']:
                return None
            if role == 'manager' and not emp_data['is_manager'] and not emp_data['is_admin']:
                return None
                
            return emp_data
        except Exception as e:
            print(f"Auth Exception: {e}")
            return None

    def change_password(self, emp_id, current_password, new_password):
        """Verify current password and update only the logged-in user's record in Snowflake."""
        user = self._execute_query(
            "SELECT PASSWORD FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s",
            (emp_id,),
            fetchone=True
        )
        if not user:
            raise Exception("User not found")

        stored_password = str(user.get('PASSWORD') or '')
        if stored_password != str(current_password):
            raise Exception("Current password is incorrect")

        updated = self._execute_query(
            "UPDATE ADLABS.AHSAN.EMPLOYEES SET PASSWORD = %s WHERE EMP_ID = %s",
            (new_password, emp_id),
            commit=True
        )
        if not updated:
            raise Exception("Failed to update password. Please try again.")
        return True

    def _map_employee(self, e):
        """Map Snowflake UPPERCASE column names to Python/Flask expected keys"""
        emp = {}
        emp['emp_id'] = e.get('EMP_ID')
        emp['emp_name'] = e.get('EMP_NAME')
        emp['emp_team'] = e.get('EMP_TEAM')
        emp['password'] = e.get('PASSWORD')
        emp['is_admin'] = bool(e.get('IS_ADMIN'))
        emp['is_manager'] = bool(e.get('IS_MANAGER'))
        emp['is_ceo'] = bool(e.get('IS_CEO'))
        emp['contract_start_date'] = str(e.get('CONTRACT_START_DATE') or '')
        emp['contract_end_date'] = str(e.get('CONTRACT_END_DATE') or '')
        emp['phone'] = e.get('PHONE')
        
        # Snowflake columns (uppercase) + template keys (mixed case) used across admin pages
        emp['Total_leaves'] = float(e.get('TOTAL_LEAVES') or 0)
        emp['Remaining_Leaves'] = float(e.get('REMAINING_LEAVES') or 0)
        emp['Leaves_This_Year'] = float(e.get('LEAVES_THIS_YEAR') or 0)
        emp['Leaves_Carried_Forward'] = float(e.get('LEAVES_CARRIED_FORWARD') or 0)
        emp['WFH_count'] = float(e.get('WFH_COUNT') or 0)
        emp['Contract_Type'] = str(e.get('CONTRACT_TYPE') or '')
        def _fmt_date(d):
            if not d: return ''
            try:
                if hasattr(d, 'strftime'):
                    return d.strftime('%d %b %Y')
                return datetime.strptime(str(d).split(' ')[0], '%Y-%m-%d').strftime('%d %b %Y')
            except Exception:
                return str(d)
        emp['Contract_Start_Date'] = _fmt_date(e.get('CONTRACT_START_DATE'))
        emp['Contract_End_Date']   = _fmt_date(e.get('CONTRACT_END_DATE'))
        
        # Raw dates for HTML <input type="date"> which requires YYYY-MM-DD
        def _raw_date(d):
            if not d: return ''
            try:
                if hasattr(d, 'strftime'):
                    return d.strftime('%Y-%m-%d')
                return str(d).split(' ')[0]
            except:
                return str(d)
        emp['Contract_Start_Date_Raw'] = _raw_date(e.get('CONTRACT_START_DATE'))
        emp['Contract_End_Date_Raw']   = _raw_date(e.get('CONTRACT_END_DATE'))

        emp['Contract_Year_Start'] = str(e.get('CONTRACT_YEAR_START') or '')
        emp['Carried_Forward_Expiry'] = str(e.get('CARRIED_FORWARD_EXPIRY') or '')

        emp['Leaves'] = emp['Leaves_This_Year']
        emp['Half_Day'] = float(e.get('HALF_DAY') or 0) * 2
        
        return emp

    def get_employees(self):
        rows = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES ORDER BY EMP_ID ASC")
        return [self._map_employee(row) for row in rows] if rows else []

    def renew_all_contracts(self):
        """
        Annual contract renewal — advances CONTRACT_START_DATE and CONTRACT_END_DATE
        by exactly one year for every employee that has both dates set.
        Called automatically on July 1st each year by the scheduler.
        Returns a list of result dicts for logging.
        """
        today = date.today()
        employees = self._execute_query("SELECT EMP_ID, EMP_NAME, CONTRACT_START_DATE, CONTRACT_END_DATE FROM ADLABS.AHSAN.EMPLOYEES")
        results = []

        for emp in (employees or []):
            emp_id   = emp.get('EMP_ID')
            emp_name = emp.get('EMP_NAME', f'ID:{emp_id}')
            cs_raw   = emp.get('CONTRACT_START_DATE')
            ce_raw   = emp.get('CONTRACT_END_DATE')

            if not cs_raw or not ce_raw:
                results.append({'emp': emp_name, 'status': 'skipped', 'reason': 'no contract dates'})
                continue

            try:
                # Parse existing dates
                cs = cs_raw if isinstance(cs_raw, date) else date.fromisoformat(str(cs_raw).split(' ')[0])
                ce = ce_raw if isinstance(ce_raw, date) else date.fromisoformat(str(ce_raw).split(' ')[0])

                # Only renew if the current contract end date has already passed or is today
                if ce > today:
                    results.append({'emp': emp_name, 'status': 'skipped', 'reason': f'contract still active until {ce}'})
                    continue

                new_cs = cs + relativedelta(years=1)
                new_ce = ce + relativedelta(years=1)

                self._execute_query(
                    """UPDATE ADLABS.AHSAN.EMPLOYEES
                       SET CONTRACT_START_DATE = %s,
                           CONTRACT_END_DATE   = %s
                       WHERE EMP_ID = %s""",
                    (new_cs.strftime('%Y-%m-%d'), new_ce.strftime('%Y-%m-%d'), emp_id),
                    commit=True
                )
                results.append({
                    'emp': emp_name,
                    'status': 'renewed',
                    'old_start': str(cs), 'old_end': str(ce),
                    'new_start': str(new_cs), 'new_end': str(new_ce)
                })
            except Exception as ex:
                results.append({'emp': emp_name, 'status': 'error', 'reason': str(ex)})

        return results

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
        updated_emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        return self._map_employee(updated_emp)

    def check_and_apply_expiry(self, emp_id):
        """Strict 1st January Expiry Rule for Carried Forward Leaves"""
        emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        if not emp: return
        
        today = date.today()
        carried = float(emp.get('LEAVES_CARRIED_FORWARD') or 0)
        
        # Check agar aaj 1st January hai
        is_january_first = (today.month == 1 and today.day == 1)
        
        # Dynamic calculation check (as a backup fallback)
        expiry_str = emp.get('CARRIED_FORWARD_EXPIRY')
        is_expired_by_date = False
        if expiry_str:
            try:
                if isinstance(expiry_str, date):
                    expiry_date = expiry_str
                else:
                    expiry_date = date.fromisoformat(str(expiry_str).split(' ')[0])
                if today >= expiry_date:
                    is_expired_by_date = True
            except: pass
            
        # Agar 1st January aa gayi hai ya dynamic expiry meet ho gayi hai, aur carried leaves bachi hui hain
        if (is_january_first or is_expired_by_date) and carried > 0:
            total = float(emp.get('TOTAL_LEAVES') or 0)
            taken = float(emp.get('LEAVES_THIS_YEAR') or 0)
            
            # Purani leaves zero ho jayengi kyunki wo sirf December tak valid thin
            new_carried = 0
            new_remaining = max(0, total - taken)
            
            self._execute_query(
                """UPDATE ADLABS.AHSAN.EMPLOYEES SET 
                    LEAVES_CARRIED_FORWARD = %s, 
                    REMAINING_LEAVES = %s, 
                    CARRIED_FORWARD_EXPIRY = NULL 
                   WHERE EMP_ID = %s""",
                (new_carried, new_remaining, emp_id), commit=True
            )
            print(f"[EXPIRY SUCCESS] ID {emp_id}: Previous year leaves expired (New Carried: {new_carried}, Remaining: {new_remaining})")
        else:
            if is_expired_by_date or is_january_first:
                self._execute_query("UPDATE ADLABS.AHSAN.EMPLOYEES SET CARRIED_FORWARD_EXPIRY = NULL WHERE EMP_ID = %s", (emp_id,), commit=True)

    def _get_leave_count_window(self, emp):
        """Date range for counting approved leave usage (contract year, else calendar year)."""
        contract_start_str = emp.get('CONTRACT_START_DATE')
        if contract_start_str:
            year_start, year_end = self.get_contract_year_window(str(contract_start_str))
            if year_start and year_end:
                return year_start, year_end
        today = date.today()
        return date(today.year, 1, 1), date(today.year, 12, 31)

    def _count_approved_requests(self, emp_id, year_start, year_end):
        counts = self._execute_query(
            """SELECT REQUEST_TYPE, COUNT(*) as CNT
               FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS
               WHERE EMP_ID = %s AND UPPER(STATUS) = 'APPROVED'
                 AND CAST(REQUEST_DATE AS DATE) >= %s
                 AND CAST(REQUEST_DATE AS DATE) <= %s
               GROUP BY REQUEST_TYPE""",
            (emp_id, year_start.strftime('%Y-%m-%d'), year_end.strftime('%Y-%m-%d'))
        )
        full_leaves = half_days = wfh = 0
        if counts:
            for row in counts:
                rtype = normalize_request_type(row.get('REQUEST_TYPE') or row.get('request_type'))
                cnt = float(row.get('CNT') or row.get('cnt') or 0)
                if rtype == 'Leave':
                    full_leaves = cnt
                elif rtype == 'Half Day':
                    half_days = cnt
                elif rtype == 'WFH':
                    wfh = cnt
        return full_leaves, half_days, wfh

    def get_leave_balance_info(self, emp_id):
        emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        if not emp: return {}
        
        contract_start_str = emp.get('CONTRACT_START_DATE')
        year_start, year_end = self.get_contract_year_window(str(contract_start_str)) if contract_start_str else (None, None)
        
        total_allowance = float(emp.get('TOTAL_LEAVES', 14.0) or 14.0)
        carried = float(emp.get('LEAVES_CARRIED_FORWARD', 0) or 0)
        total_available = total_allowance + carried
        
        # Use EMPLOYEES table counters directly (synced when requests are approved)
        leaves_taken = float(emp.get('LEAVES_THIS_YEAR', 0) or 0)
        wfh_count = float(emp.get('WFH_COUNT', 0) or 0)
        remaining_leaves = float(emp.get('REMAINING_LEAVES', 0) or 0)
        # Multiply by 2 because DB stores deducted leave (e.g. 1 means 2 half days)
        half_days_taken = float(emp.get('HALF_DAY', 0) or 0) * 2
        
        return {
            'contract_year_start': year_start.strftime('%d %b %Y') if year_start else 'N/A',
            'contract_year_end': year_end.strftime('%d %b %Y') if year_end else 'N/A',
            'total_leaves': total_allowance,
            'total_allotted': total_allowance,
            'carried_forward': carried,
            'total_available': total_available,
            'leaves_taken_this_year': leaves_taken,
            'half_days_taken': half_days_taken,
            'remaining_leaves': remaining_leaves,
            'wfh_count': int(wfh_count)
        }

    def update_employee_counters(self, emp_id, request_type=None, action='approve'):
        try:
            emp_id_int = int(emp_id)
            if not request_type:
                print(f"[SYNC SKIP] ID {emp_id_int}: Recalculation skipped to preserve manual data.")
                return True
            
            request_type_normalized = normalize_request_type(request_type)
            multiplier = 1 if action == 'approve' else -1
            
            if request_type_normalized == 'WFH':
                self._execute_query(
                    """UPDATE ADLABS.AHSAN.EMPLOYEES 
                       SET WFH_COUNT = COALESCE(WFH_COUNT, 0) + %s 
                       WHERE EMP_ID = %s""",
                    (1 * multiplier, emp_id_int), commit=True
                )
            elif request_type_normalized == 'Leave':
                self._execute_query(
                    """UPDATE ADLABS.AHSAN.EMPLOYEES 
                       SET REMAINING_LEAVES = COALESCE(REMAINING_LEAVES, 0) - %s, 
                           LEAVES_THIS_YEAR = COALESCE(LEAVES_THIS_YEAR, 0) + %s 
                       WHERE EMP_ID = %s""",
                    (1.0 * multiplier, 1.0 * multiplier, emp_id_int), commit=True
                )
            elif request_type_normalized == 'Half Day':
                self._execute_query(
                    """UPDATE ADLABS.AHSAN.EMPLOYEES 
                       SET REMAINING_LEAVES = COALESCE(REMAINING_LEAVES, 0) - %s, 
                           LEAVES_THIS_YEAR = COALESCE(LEAVES_THIS_YEAR, 0) + %s, 
                           HALF_DAY = COALESCE(HALF_DAY, 0) + %s 
                       WHERE EMP_ID = %s""",
                    (0.5 * multiplier, 0.5 * multiplier, 0.5 * multiplier, emp_id_int), commit=True
                )
            
            print(f"[SYNC SUCCESS] ID {emp_id_int}: Updated incrementally for {request_type} ({action})")
            return True
        except Exception as e:
            print(f"[SYNC ERROR] {e}")
            return False

    def sync_all_employee_counters(self):
        print("[SYNC ALL] sync_all_employee_counters skipped to preserve manually entered data.")
        return 0

    def get_leave_balance_cached(self, emp_id, cache):
        key = str(emp_id)
        if key not in cache:
            cache[key] = self.get_leave_balance_info(emp_id)
        return cache.get(key) or {}

    def refund_employee_counters(self, emp_id, request_type=None):
        return self.update_employee_counters(emp_id, request_type, action='cancel')

    def log_approval_action(self, emp_id, emp_name, request_type, request_date, status, manager_name):
        return self.db.log_approval_action(emp_id, emp_name, request_type, request_date, status, manager_name)

    def mark_wfh_leave(self, emp_id, emp_name, emp_team, date, request_type, reason, status='Pending', manager_name=''):
        try: emp_id_int = int(emp_id)
        except: emp_id_int = emp_id
        
        date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        
        # Check if there is an existing approved request on that date and refund it first
        existing = self._execute_query(
            """SELECT REQUEST_TYPE FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS 
               WHERE EMP_ID = %s 
                 AND CAST(REQUEST_DATE AS DATE) = %s 
                 AND UPPER(STATUS) = 'APPROVED' LIMIT 1""",
            (emp_id_int, date_str), fetchone=True
        )
        if existing:
            self.refund_employee_counters(emp_id_int, existing.get('REQUEST_TYPE') or existing.get('request_type'))

        self._execute_query(
            "DELETE FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE EMP_ID = %s AND (CAST(REQUEST_DATE AS DATE) = %s OR TO_VARCHAR(REQUEST_DATE, 'YYYY-MM-DD') = %s)",
            (emp_id_int, date_str, date_str), commit=True
        )

        self.db.mark_request(emp_id_int, date_str, request_type, reason, status, manager_name if status == 'Approved' else None)
        
        if status == 'Approved':
            self.update_employee_counters(emp_id_int, request_type, action='approve')
            self.log_approval_action(emp_id_int, emp_name, request_type, date_str, 'Approved', manager_name or emp_name)
        
        return True

    def get_notifications(self, filter_date=None, limit=None):
        if filter_date is None: filter_date = date.today()
        query = """
        SELECT r.*, e.EMP_NAME, e.EMP_TEAM
        FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
        JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
        WHERE UPPER(r.STATUS) = 'PENDING' 
           OR CAST(r.SUBMITTED_AT AS DATE) = %s
        ORDER BY CASE WHEN UPPER(r.STATUS) = 'PENDING' THEN 0 ELSE 1 END, r.SUBMITTED_AT DESC
        """
        rows = self._execute_query(query, (filter_date.strftime('%Y-%m-%d'),))
        
        notifications = []
        balance_cache = {}
        if rows:
            for row in rows:
                req_date = row.get('REQUEST_DATE')
                if isinstance(req_date, (datetime, date)):
                    req_date_obj = req_date.date() if isinstance(req_date, datetime) else req_date
                else:
                    try:
                        req_date_obj = datetime.strptime(str(req_date).split(' ')[0], '%Y-%m-%d').date()
                    except:
                        req_date_obj = date.today()

                req_emp_id = row.get('EMP_ID')
                leave_bal = self.get_leave_balance_cached(req_emp_id, balance_cache)
                notifications.append({
                    'date': req_date_obj.strftime('%Y-%m-%d'),
                    'display_date': req_date_obj.strftime('%d-%b-%Y'),
                    'emp_id': req_emp_id,
                    'emp_name': row.get('EMP_NAME'),
                    'team': row.get('EMP_TEAM'),
                    'emp_balance': leave_bal.get('remaining_leaves', 'N/A'),
                    'type': normalize_request_type(row.get('REQUEST_TYPE')),
                    'reason': row.get('REASON'),
                    'timestamp': row.get('SUBMITTED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('SUBMITTED_AT'), 'strftime', None) else str(row.get('SUBMITTED_AT')),
                    'status': normalize_status(row.get('STATUS'))
                })
        return notifications

    def get_pending_requests(self, days_back=30, days_forward=365, req_status='Pending'):
        query = """
                SELECT r.*, e.EMP_NAME, e.EMP_TEAM as team
                FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
                JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
                WHERE UPPER(r.STATUS) = UPPER(%s) AND UPPER(r.REQUEST_TYPE) != 'SCHEDULE'
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
                    'type': normalize_request_type(row.get('REQUEST_TYPE')),
                    'reason': row.get('REASON'),
                    'timestamp': row.get('SUBMITTED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('SUBMITTED_AT'), 'strftime', None) else str(row.get('SUBMITTED_AT')),
                    'status': normalize_status(row.get('STATUS'))
                })
        return requests_list

    def get_all_requests(self, statuses=None):
        if statuses is None:
            statuses = ['Pending', 'Approved']
        
        upper_statuses = [s.upper() for s in statuses]
        placeholders = ', '.join(['%s'] * len(upper_statuses))
        query = f"""
                SELECT r.*, e.EMP_NAME, e.EMP_TEAM as team
                FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS r
                JOIN ADLABS.AHSAN.EMPLOYEES e ON r.EMP_ID = e.EMP_ID
                WHERE UPPER(r.STATUS) IN ({placeholders})
                ORDER BY r.REQUEST_ID DESC
                """
        rows = self._execute_query(query, tuple(upper_statuses))
        
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
                    'type': normalize_request_type(row.get('REQUEST_TYPE')),
                    'reason': row.get('REASON'),
                    'timestamp': row.get('SUBMITTED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('SUBMITTED_AT'), 'strftime', None) else str(row.get('SUBMITTED_AT')),
                    'status': normalize_status(row.get('STATUS'))
                })
        return requests_list

    def update_request_status(self, request_date_str, emp_id, request_type, timestamp, new_status, manager_name):
        import time
        import threading
        print(f"[DEBUG] update_request_status started")
        
        # Fix: String date comparison ko direct '=' se hatakar CAST(REQUEST_DATE AS DATE) kiya taake Snowflake properly match kare
        success = self._execute_query(
            """UPDATE ADLABS.AHSAN.ATTENDANCE_REQUESTS 
               SET STATUS = %s, APPROVED_BY = %s 
               WHERE EMP_ID = %s 
                 AND CAST(REQUEST_DATE AS DATE) = %s 
                 AND UPPER(REQUEST_TYPE) = UPPER(%s) 
                 AND UPPER(STATUS) = 'PENDING'""",
            (new_status, manager_name, emp_id, request_date_str, request_type), commit=True
        )
        
        if success:
            if new_status == 'Approved':
                self.update_employee_counters(emp_id, request_type, action='approve')
            
            def log_action_background():
                try:
                    emp_name = self._execute_query("SELECT EMP_NAME FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
                    self.log_approval_action(emp_id, emp_name.get('EMP_NAME') if emp_name else str(emp_id), request_type, request_date_str, new_status, manager_name)
                except Exception as e:
                    print(f"[DEBUG] Background logging error: {e}")
            
            threading.Thread(target=log_action_background, daemon=True).start()
            return True
        raise Exception("Could not find the specific request to update.")

    def cancel_request(self, request_date_str, emp_id, timestamp, cancelled_by):
        # Fix: SELECT statement mein CAST apply kiya date string matching ke liye
        req = self._execute_query(
            """SELECT STATUS, REQUEST_TYPE 
               FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS 
               WHERE EMP_ID = %s 
                 AND CAST(REQUEST_DATE AS DATE) = %s 
                 AND UPPER(STATUS) IN ('APPROVED', 'PENDING') LIMIT 1""",
            (emp_id, request_date_str), fetchone=True
        )
        if not req:
            raise Exception("Could not find the specific request to cancel.")
            
        current_status = req.get('STATUS')
        request_type = req.get('REQUEST_TYPE')
        
        if current_status and str(current_status).upper() == 'APPROVED':
            self.refund_employee_counters(emp_id, request_type)
            
        # Fix: UPDATE statement mein bhi CAST lagaya
        self._execute_query(
            """UPDATE ADLABS.AHSAN.ATTENDANCE_REQUESTS 
               SET STATUS = 'Cancelled', APPROVED_BY = %s 
               WHERE EMP_ID = %s 
                 AND CAST(REQUEST_DATE AS DATE) = %s""",
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
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Only return actual attendance activity — exclude SCHEDULE entries (Beyond Schedule assignments)
        rows = self._execute_query(
            """SELECT * FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS 
               WHERE EMP_ID = %s 
                 AND CAST(REQUEST_DATE AS DATE) >= %s 
                 AND CAST(REQUEST_DATE AS DATE) <= %s
                 AND UPPER(REQUEST_TYPE) NOT IN ('SCHEDULE')
               ORDER BY REQUEST_DATE ASC, SUBMITTED_AT ASC""",
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
                    'type': normalize_request_type(row.get('REQUEST_TYPE')),
                    'reason': row.get('REASON'),
                    'timestamp': row.get('SUBMITTED_AT').strftime('%Y-%m-%d %H:%M:%S') if getattr(row.get('SUBMITTED_AT'), 'strftime', None) else str(row.get('SUBMITTED_AT')),
                    'status': normalize_status(row.get('STATUS'))
                })
        return records

    def add_employee(self, emp_name, emp_team, is_admin, is_manager, contract_type, contract_start_date, contract_end_date, total_leaves, password='SecurePass2026!'):
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

    def get_employee_by_id(self, emp_id) -> dict:
        emp = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE EMP_ID = %s", (emp_id,), fetchone=True)
        return self._map_employee(emp) if emp else {}

    def get_all_managers(self) -> list:
        rows = self._execute_query("SELECT * FROM ADLABS.AHSAN.EMPLOYEES WHERE IS_MANAGER = TRUE")
        return [self._map_employee(r) for r in rows] if rows else []

    def get_daily_attendance_summary(self, summary_date):
        teams = {}
        all_emps = self.get_employees()
        
        for e in all_emps:
            team = e.get('emp_team', 'Unknown')
            if team not in teams:
                teams[team] = {'wfh': [], 'leave': [], 'half_day': [], 'no_request': []}
                
        # Fix: Daily Summary fetching query mein bhi CAST apply kar diya taake dashboard breakdown accurate ho jaye
        reqs = self._execute_query(
            """SELECT EMP_ID, REQUEST_TYPE 
               FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS 
               WHERE CAST(REQUEST_DATE AS DATE) = %s 
                 AND UPPER(STATUS) IN ('APPROVED', 'PENDING')""", 
            (summary_date.strftime('%Y-%m-%d'),)
        )
        filed_by_emp = {}
        if reqs:
            for r in reqs:
                filed_by_emp[str(r.get('EMP_ID'))] = normalize_request_type(r.get('REQUEST_TYPE'))
                
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

    def get_overstock_team_members(self):
        employees = self.get_employees()
        overstock = [e for e in employees if e.get('emp_team', '').lower() == 'overstock']
        return overstock

    def save_shift_schedule(self, valid_from, valid_until, schedule_data, meeting_lead_week1, meeting_lead_week2, weekly_report_week1, weekly_report_week2):
        try:
            self._execute_query(
                "DELETE FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS WHERE REQUEST_TYPE = 'Schedule' AND CAST(REQUEST_DATE AS DATE) = %s",
                (valid_from,), commit=True
            )
            
            for item in schedule_data:
                shift_name = item.get('shift')
                emp_id = item.get('emp_id')
                
                self._execute_query(
                    """INSERT INTO ADLABS.AHSAN.ATTENDANCE_REQUESTS 
                    (EMP_ID, REQUEST_DATE, REQUEST_TYPE, REASON, STATUS, SUBMITTED_AT) 
                    VALUES (%s, %s, 'Schedule', %s, 'Approved', CURRENT_TIMESTAMP())""",
                    (emp_id, valid_from, f"main:{shift_name}"), commit=True
                )
            
            if meeting_lead_week1:
                self._execute_query(
                    """INSERT INTO ADLABS.AHSAN.ATTENDANCE_REQUESTS 
                    (EMP_ID, REQUEST_DATE, REQUEST_TYPE, REASON, STATUS, SUBMITTED_AT) 
                    VALUES (%s, %s, 'Schedule', %s, 'Approved', CURRENT_TIMESTAMP())""",
                    (meeting_lead_week1, valid_from, "meeting_lead_week1:Meeting Lead"), commit=True
                )
            if meeting_lead_week2:
                self._execute_query(
                    """INSERT INTO ADLABS.AHSAN.ATTENDANCE_REQUESTS 
                    (EMP_ID, REQUEST_DATE, REQUEST_TYPE, REASON, STATUS, SUBMITTED_AT) 
                    VALUES (%s, %s, 'Schedule', %s, 'Approved', CURRENT_TIMESTAMP())""",
                    (meeting_lead_week2, valid_from, "meeting_lead_week2:Meeting Lead"), commit=True
                )
            
            if weekly_report_week1:
                self._execute_query(
                    """INSERT INTO ADLABS.AHSAN.ATTENDANCE_REQUESTS 
                    (EMP_ID, REQUEST_DATE, REQUEST_TYPE, REASON, STATUS, SUBMITTED_AT) 
                    VALUES (%s, %s, 'Schedule', %s, 'Approved', CURRENT_TIMESTAMP())""",
                    (weekly_report_week1, valid_from, "weekly_report_week1:Weekly Report"), commit=True
                )
            if weekly_report_week2:
                self._execute_query(
                    """INSERT INTO ADLABS.AHSAN.ATTENDANCE_REQUESTS 
                    (EMP_ID, REQUEST_DATE, REQUEST_TYPE, REASON, STATUS, SUBMITTED_AT) 
                    VALUES (%s, %s, 'Schedule', %s, 'Approved', CURRENT_TIMESTAMP())""",
                    (weekly_report_week2, valid_from, "weekly_report_week2:Weekly Report"), commit=True
                )
            
            return True
        except Exception as e:
            print(f"Error saving shift schedule: {e}")
            return False

    def get_shift_schedules(self, valid_from=None):
        try:
            if valid_from:
                rows = self._execute_query(
                    """SELECT * FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS 
                    WHERE REQUEST_TYPE = 'Schedule' AND CAST(REQUEST_DATE AS DATE) = %s""",
                    (valid_from,)
                )
            else:
                rows = self._execute_query(
                    """SELECT * FROM ADLABS.AHSAN.ATTENDANCE_REQUESTS 
                    WHERE REQUEST_TYPE = 'Schedule' ORDER BY REQUEST_DATE DESC LIMIT 100"""
                )
            
            schedules = []
            if rows:
                for row in rows:
                    reason = row.get('REASON', '')
                    if ':' in reason:
                        schedule_type, shift_name = reason.split(':', 1)
                    else:
                        schedule_type = 'main'
                        shift_name = reason
                    
                    schedules.append({
                        'valid_from': row.get('REQUEST_DATE'),
                        'valid_until': row.get('REQUEST_DATE'),
                        'shift_name': shift_name,
                        'emp_id': row.get('EMP_ID'),
                        'schedule_type': schedule_type,
                        'submitted_at': row.get('SUBMITTED_AT')
                    })
            return schedules
        except Exception as e:
            print(f"Error getting shift schedules: {e}")
            return []