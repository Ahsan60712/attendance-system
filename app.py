from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from attendance_manager import WFHLeaveManager
from datetime import date, datetime, timedelta
import os
import logging
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

import whatsapp_notifier as wa

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Initialize the WFH/Leave manager
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
manager = WFHLeaveManager(BASE_PATH)

# ── APScheduler — Automated Daily Summary & Absent Alert ─────────────────────
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

@app.route('/privacy-policy')
def privacy_policy():
    """Privacy policy page for Meta API compliance"""
    return render_template('privacy_policy.html')

def _send_daily_summaries():
    """Background job: build per-team attendance summary and WhatsApp each manager."""
    today = date.today()
    # Skip weekends
    if today.weekday() >= 5:
        print(f"[Scheduler] Skipping daily summary — it's a weekend ({today}).")
        return

    print(f"[Scheduler] ▶ Sending daily attendance summaries for {today}…")
    try:
        teams = manager.get_daily_attendance_summary(today)
        all_managers = manager.get_all_managers()

        for mgr in all_managers:
            mgr_phone = mgr.get('phone', '')
            mgr_name = mgr.get('emp_name', 'Manager')
            mgr_team = str(mgr.get('emp_team', '')).strip()

            if not mgr_phone or pd.isna(mgr_phone) or str(mgr_phone).strip() == '':
                print(f"[Scheduler] Skipping {mgr_name} — no phone number.")
                continue

            team_data = teams.get(mgr_team, {})
            wa.send_daily_summary(
                manager_phone=str(mgr_phone),
                manager_name=mgr_name,
                summary_date=today,
                team_name=mgr_team or 'All',
                wfh_list=team_data.get('wfh', []),
                leave_list=team_data.get('leave', []),
                half_day_list=team_data.get('half_day', []),
                absent_list=team_data.get('no_request', [])
            )
        print(f"[Scheduler] ✅ Daily summaries sent for {today}.")
    except Exception as e:
        print(f"[Scheduler] ❌ Error sending daily summaries: {e}")


def _send_absent_alerts():
    """Background job: alert each manager about employees with no request filed."""
    today = date.today()
    if today.weekday() >= 5:
        print(f"[Scheduler] Skipping absent alert — it's a weekend ({today}).")
        return

    print(f"[Scheduler] ▶ Sending absent-employee alerts for {today}…")
    try:
        teams = manager.get_daily_attendance_summary(today)
        all_managers = manager.get_all_managers()

        for mgr in all_managers:
            mgr_phone = mgr.get('phone', '')
            mgr_name = mgr.get('emp_name', 'Manager')
            mgr_team = str(mgr.get('emp_team', '')).strip()

            if not mgr_phone or pd.isna(mgr_phone) or str(mgr_phone).strip() == '':
                continue

            team_data = teams.get(mgr_team, {})
            absent = team_data.get('no_request', [])
            if absent:
                # ── Notify Manager ──
                wa.send_absent_alert(
                    manager_phone=str(mgr_phone),
                    manager_name=mgr_name,
                    absent_employees=absent,
                    team_name=mgr_team or 'All',
                    alert_date=today
                )

                # ── Notify Each Absent Employee Directly ──
                employees = manager.get_employees()
                for emp_name in absent:
                    # Find employee data to get their phone number
                    emp_info = next((e for e in employees if str(e.get('emp_name')).strip() == str(emp_name).strip()), {})
                    emp_phone = emp_info.get('phone', '')
                    if emp_phone and not pd.isna(emp_phone):
                        wa.notify_employee_absence(
                            emp_phone=str(emp_phone),
                            emp_name=emp_name,
                            alert_date=today
                        )
        print(f"[Scheduler] ✅ Absent alerts sent for {today}.")
    except Exception as e:
        print(f"[Scheduler] ❌ Error sending absent alerts: {e}")


# Schedule the jobs (Pakistan time = UTC+5)
SUMMARY_HOUR = int(os.environ.get('DAILY_SUMMARY_HOUR', 9))
SUMMARY_MINUTE = int(os.environ.get('DAILY_SUMMARY_MINUTE', 30))
ALERT_HOUR = int(os.environ.get('ABSENT_ALERT_HOUR', 11))
ALERT_MINUTE = int(os.environ.get('ABSENT_ALERT_MINUTE', 0))

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    _send_daily_summaries,
    trigger='cron',
    hour=SUMMARY_HOUR,
    minute=SUMMARY_MINUTE,
    day_of_week='mon-fri',
    id='daily_summary',
    name='Daily Attendance Summary'
)
scheduler.add_job(
    _send_absent_alerts,
    trigger='cron',
    hour=ALERT_HOUR,
    minute=ALERT_MINUTE,
    day_of_week='mon-fri',
    id='absent_alert',
    name='Absent Employee Alert'
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))
print(f"[Scheduler] ✅ Started — Daily summary at {SUMMARY_HOUR:02d}:{SUMMARY_MINUTE:02d}, Absent alert at {ALERT_HOUR:02d}:{ALERT_MINUTE:02d} (Mon–Fri)")

@app.route('/')
def index():
    """Landing page with links to employee and admin login"""
    return render_template('index.html')

# ===== EMPLOYEE ROUTES =====

@app.route('/employee-login', methods=['GET', 'POST'])
def employee_login():
    """Employee login page"""
    if request.method == 'POST':
        emp_name = request.form.get('emp_name')
        password = request.form.get('password')
        
        try:
            user = manager.authenticate_user(emp_name, password)
            if user:
                session['logged_in'] = True
                
                # Still check if they are technically a manager acting as an employee
                if user.get('is_manager', 0) == 1:
                    session['user_type'] = 'manager'
                    session['emp_id'] = user['emp_id']
                    session['emp_name'] = user['emp_name']
                    session['emp_team'] = user.get('emp_team', '')
                    return redirect(url_for('manager_dashboard'))
                else:    
                    session['user_type'] = 'employee'
                    session['emp_id'] = user['emp_id']
                    session['emp_name'] = user['emp_name']
                    session['emp_team'] = user.get('emp_team', '')
                    return redirect(url_for('employee_dashboard'))
            else:
                flash('Invalid credentials', 'error')
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
    
    return render_template('employee_login.html')

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Change password page"""
    if not session.get('emp_id'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            try:
                manager.change_password(session.get('emp_id'), new_password)
                # Redirect based on role
                if session.get('user_type') == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif session.get('user_type') == 'manager':
                    return redirect(url_for('manager_dashboard'))
                else:
                    return redirect(url_for('employee_dashboard'))
            except Exception as e:
                flash(f'Error changing password: {str(e)}', 'error')
                
    return render_template('change_password.html')

@app.route('/employee-dashboard')
def employee_dashboard():
    """Employee dashboard"""
    if session.get('user_type') != 'employee':
        return redirect(url_for('employee_login'))
    
    emp_id = session.get('emp_id')
    today = date.today()
    
    # Auto-rollover contract year leaves if anniversary passed
    manager.check_and_rollover_leaves(emp_id)
    manager.check_and_apply_expiry(emp_id)

    # Get all employees to find current emp data
    employees = manager.get_employees()
    current_emp = next((e for e in employees if str(e['emp_id']) == str(emp_id)), {})

    # Rich leave balance for display
    leave_balance = manager.get_leave_balance_info(emp_id)
    
    # --- History Filtering Logic ---
    filter_type = request.args.get('filter_type', 'default')
    
    if filter_type == 'monthly':
        month = int(request.args.get('month', today.month))
        year = int(request.args.get('year', today.year))
        # First day of month
        start_date = date(year, month, 1)
        # Last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
            
    elif filter_type == 'yearly':
        year = int(request.args.get('year', today.year))
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
    elif filter_type == 'custom':
        start_str = request.args.get('start_date')
        end_str = request.args.get('end_date')
        if start_str and end_str:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        else:
            start_date = today - timedelta(days=30)
            end_date = today + timedelta(days=365)
            
    else: # Default view (Last 30 days + Future)
        start_date = today - timedelta(days=30)
        end_date = today + timedelta(days=365)

    records = manager.get_employee_records(emp_id, start_date, end_date)
    
    return render_template('employee_dashboard.html', 
                         emp_name=session.get('emp_name'),
                         emp_data=current_emp,
                         leave_balance=leave_balance,
                         records=records,
                         today=today.strftime('%Y-%m-%d'),
                         filter_type=filter_type,
                         filter_start=start_date.strftime('%Y-%m-%d'),
                         filter_end=end_date.strftime('%Y-%m-%d'))

@app.route('/mark-request', methods=['POST'])
def mark_request():
    """Handle WFH/Leave request from employee or manager"""
    user_type = session.get('user_type')
    if user_type not in ['employee', 'manager']:
        return redirect(url_for('employee_login'))
    
    # Managers are auto-approved for their own requests
    status = 'Approved' if user_type == 'manager' else 'Pending'
    manager_name = session.get('emp_name') if user_type == 'manager' else ''
    redirect_target = 'manager_dashboard' if user_type == 'manager' else 'employee_dashboard'
    
    try:
        request_type = request.form.get('request_type')  # 'WFH' or 'Leave' or 'Half Day'
        reason = request.form.get('reason')
        start_date_str = request.form.get('date', date.today().strftime('%Y-%m-%d'))
        end_date_str = request.form.get('end_date') # Optional end date
        
        if not reason or not reason.strip():
            flash('Reason is required', 'error')
            return redirect(url_for(redirect_target))
        
        start_date = date.fromisoformat(start_date_str)
        
        # Determine date range
        if end_date_str and request_type == 'Leave':
            end_date = date.fromisoformat(end_date_str)
            if end_date < start_date:
                flash('End date cannot be before start date', 'error')
                return redirect(url_for(redirect_target))
        else:
            end_date = start_date

        # Iterate through dates
        current_date = start_date
        count = 0
        while current_date <= end_date:
            try:
                manager.mark_wfh_leave(
                    emp_id=session.get('emp_id'),
                    emp_name=session.get('emp_name'),
                    emp_team=session.get('emp_team'),
                    date=current_date,
                    request_type=request_type,
                    reason=reason,
                    status=status,
                    manager_name=manager_name
                )
                count += 1
            except Exception as e:
                flash(f'Error on {current_date.strftime("%Y-%m-%d")}: {str(e)}', 'danger')
                return redirect(url_for(redirect_target))
            
            current_date += timedelta(days=1)
            
        success_msg = f'{request_type} request submitted successfully for {count} day(s)!'
        if user_type == 'manager':
            success_msg = f'{request_type} applied successfully (Auto-Approved)!'

        # ── WhatsApp: notify the team manager about the new request ──────────
        if user_type == 'employee':
            try:
                emp_team = session.get('emp_team', '')
                team_manager = manager.get_manager_for_team(emp_team)
                # ── WhatsApp: notify the team manager about the new request ──────────
                mgr_phone = team_manager.get('phone', '')
                print(f"[DEBUG] Triggering WhatsApp to Manager: {mgr_phone}")
                wa_success = wa.notify_manager_new_request(
                    manager_phone=mgr_phone or '',
                    manager_name=team_manager.get('emp_name', 'Manager'),
                    emp_name=session.get('emp_name', ''),
                    request_type=request_type,
                    request_date=f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}" if end_date != start_date else start_date.strftime('%d %b %Y'),
                    reason=reason
                )
                
                # ── Notify the Employee themselves (Confirmation) ──
                emp_id = session.get('emp_id')
                emp_phone = manager.get_employee_phone(emp_id)
                if emp_phone:
                    wa.notify_employee_request_submitted(
                        emp_phone=emp_phone,
                        emp_name=session.get('emp_name', ''),
                        request_type=request_type,
                        request_date=f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}" if end_date != start_date else start_date.strftime('%d %b %Y')
                    )
            except Exception as wa_err:
                flash(f"WhatsApp Error: {str(wa_err)}", 'danger')
                print(f"[WhatsApp] Could not notify manager or employee: {wa_err}")
        # ─────────────────────────────────────────────────────────────────────

        flash(success_msg, 'success')
        return redirect(url_for(redirect_target))
        
    except Exception as e:
        flash(f'Error submitting request: {str(e)}', 'error')
        return redirect(url_for(redirect_target))

# ===== MANAGER ROUTES =====

@app.route('/manager-login', methods=['GET', 'POST'])
def manager_login():
    """Manager login page"""
    if request.method == 'POST':
        emp_name = request.form.get('emp_name')
        password = request.form.get('password')
        
        try:
            # Check manager authentication
            user = manager.authenticate_user(emp_name, password, role='manager')
            if user:
                session['logged_in'] = True
                session['user_type'] = 'manager'
                session['emp_id'] = user['emp_id']
                session['emp_name'] = user['emp_name']
                session['emp_team'] = user['emp_team']
                return redirect(url_for('manager_dashboard'))
            else:
                flash('Invalid manager credentials', 'error')
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
    
    return render_template('manager_login.html')

@app.route('/manager-dashboard')
def manager_dashboard():
    """Manager dashboard showing pending requests and personal application form"""
    try:
        if session.get('user_type') not in ['manager', 'admin']:
            return redirect(url_for('employee_login'))
        
        emp_id = session.get('emp_id')
        today = date.today()

        # Get filter dates from query params
        start_date_str = request.args.get('start_date', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date_str = request.args.get('end_date', today.strftime('%Y-%m-%d'))

        # Auto-rollover contract year leaves if anniversary passed
        manager.check_and_rollover_leaves(emp_id)
        manager.check_and_apply_expiry(emp_id)
        
        # Get manager's own data from the master list
        employees = manager.get_employees()
        emp_id = session.get('emp_id')
        current_emp = next((e for e in employees if str(e.get('emp_id')) == str(emp_id)), {})
        
        # If for some reason manager isn't found in employees list, use session name
        if not current_emp:
            current_emp = {
                'emp_id': emp_id,
                'emp_name': session.get('emp_name', 'Manager'),
                'emp_team': session.get('emp_team', 'General')
            }

        # Rich leave balance for display
        leave_balance = manager.get_leave_balance_info(emp_id)
        
        # Get pending requests for approval (from others)
        all_pending_requests = manager.get_pending_requests(req_status='Pending')
        # DEBUG: Let's see what's happening
        print(f"DEBUG: Manager ID: {emp_id}, Team from Session: {session.get('emp_team')}, Team from DB: {current_emp.get('emp_team')}")
        
        emp_team = (current_emp.get('emp_team') or session.get('emp_team', '')).strip().lower()
        
        if session.get('user_type') == 'admin':
            pending_requests = [req for req in all_pending_requests if str(req.get('emp_id')) != str(emp_id)]
        else:
            pending_requests = []
            for req in all_pending_requests:
                req_team = str(req.get('team', '')).strip().lower()
                print(f"DEBUG: Comparing Req Team '{req_team}' with Manager Team '{emp_team}'")
                if req_team == emp_team and str(req.get('emp_id')) != str(emp_id):
                    pending_requests.append(req)
        
        print(f"DEBUG: Found {len(pending_requests)} requests for this manager.")
        
        # Attach employee balance to each pending request
        for req in pending_requests:
            req_emp_id = req.get('emp_id')
            req_emp_data = next((e for e in employees if str(e['emp_id']) == str(req_emp_id)), {})
            # Attach the remaining leaves specifically
            req['emp_balance'] = req_emp_data.get('Remaining_Leaves', 'N/A')
            req['total_allotted'] = req_emp_data.get('Total_leaves', 14)
            
        # Get approved requests (from others) with date filtering
        all_approved_requests = manager.get_pending_requests(req_status='Approved')
        
        # Filter by team first
        if session.get('user_type') == 'admin':
            team_approved = [req for req in all_approved_requests if str(req.get('emp_id')) != str(emp_id)]
        else:
            emp_team = current_emp.get('emp_team', '')
            team_approved = [req for req in all_approved_requests if req.get('team') == emp_team and str(req.get('emp_id')) != str(emp_id)]

        # Then filter by date range
        approved_requests = []
        try:
            sd = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            ed = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            for req in team_approved:
                req_date_raw = req.get('date')
                if req_date_raw:
                    # Robust parsing: handle both string and date objects
                    if isinstance(req_date_raw, (date, datetime)):
                        req_date = req_date_raw.date() if isinstance(req_date_raw, datetime) else req_date_raw
                    else:
                        req_date = datetime.strptime(str(req_date_raw).split(' ')[0], '%Y-%m-%d').date()
                    
                    if sd <= req_date <= ed:
                        approved_requests.append(req)
        except Exception as e:
            print(f"Filter Error: {e}")
            approved_requests = team_approved[:20] # Final Fallback
        
        # Get manager's OWN records for history display
        my_records = manager.get_employee_records(emp_id, today - timedelta(days=30), today + timedelta(days=365))
        
        # Ensure leave_balance is a dictionary and has required keys
        if not isinstance(leave_balance, dict):
            leave_balance = {}
        
        return render_template('manager_dashboard.html', 
                               manager_name=session.get('emp_name', 'Manager'),
                               emp_data=current_emp or {},
                               leave_balance=leave_balance,
                               requests=pending_requests,
                               approved_requests=approved_requests,
                               my_records=my_records,
                               start_date=start_date_str,
                               end_date=end_date_str,
                               total_allotted=leave_balance.get('total_allotted', 0),
                               carried_forward=leave_balance.get('carried_forward', 0),
                               remaining_leaves=leave_balance.get('remaining_leaves', 0),
                               today=today.strftime('%Y-%m-%d'))
    except Exception as e:
        return f"<h2>⚠️ Dashboard Crash!</h2><p>Error Type: {type(e).__name__}</p><p>Message: {str(e)}</p>"

@app.route('/action-request', methods=['POST'])
def action_request():
    """Approve or Reject a pending request"""
    if session.get('user_type') not in ['manager', 'admin']:
        return redirect(url_for('employee_login'))
        
    emp_id = request.form.get('emp_id')
    req_date = request.form.get('date')
    req_type = request.form.get('type')
    timestamp = request.form.get('timestamp')
    action = request.form.get('action') # 'Approve' or 'Reject'
    
    try:
        new_status = 'Approved' if action == 'Approve' else 'Rejected'
        manager.update_request_status(
            request_date_str=req_date, 
            emp_id=emp_id, 
            request_type=req_type,
            timestamp=timestamp, 
            new_status=new_status, 
            manager_name=session.get('emp_name')
        )
        flash(f'Request successfully {new_status.lower()}!', 'success')

        # ── WhatsApp: notify employee of the decision ─────────────────────
        try:
            emp_phone = manager.get_employee_phone(emp_id)
            if emp_phone:
                # Get employee name from the request form or records
                employees = manager.get_employees()
                emp_info = next((e for e in employees if str(e['emp_id']) == str(emp_id)), {})
                wa.notify_employee_decision(
                    emp_phone=emp_phone,
                    emp_name=emp_info.get('emp_name', f'Employee #{emp_id}'),
                    manager_name=session.get('emp_name', 'Manager'),
                    request_type=req_type,
                    request_date=req_date,
                    decision=new_status
                )
        except Exception as wa_err:
            print(f"[WhatsApp] Could not notify employee: {wa_err}")
        # ─────────────────────────────────────────────────────────────────

    except Exception as e:
        flash(f'Error processing request: {str(e)}', 'danger')
        
    # Redirect back to whoever called it (Admin might use this too)
    return redirect(request.referrer or url_for('manager_dashboard'))

@app.route('/cancel-request', methods=['POST'])
def cancel_request():
    """Cancel a pending or approved request"""
    if not session.get('logged_in'):
        return redirect(url_for('index'))
        
    emp_id = request.form.get('emp_id')
    req_date = request.form.get('date')
    timestamp = request.form.get('timestamp')
    
    # Employees can only cancel their OWN requests.
    if session.get('user_type') == 'employee' and str(emp_id) != str(session.get('emp_id')):
        flash('You are not authorized to cancel this request.', 'danger')
        return redirect(request.referrer or url_for('employee_dashboard'))
        
    try:
        manager.cancel_request(
            request_date_str=req_date, 
            emp_id=emp_id, 
            timestamp=timestamp, 
            cancelled_by=session.get('emp_name')
        )
        flash('Request successfully cancelled!', 'success')

        # ── WhatsApp: notify the team manager of the cancellation ─────────
        try:
            employees = manager.get_employees()
            emp_info = next((e for e in employees if str(e['emp_id']) == str(emp_id)), {})
            emp_team = emp_info.get('emp_team', '')
            req_type_cancelled = request.form.get('type', 'Request')
            if emp_team:
                team_manager = manager.get_manager_for_team(emp_team)
                mgr_phone = team_manager.get('phone', '')
                if mgr_phone and str(emp_id) != str(session.get('emp_id')):
                    # Only notify manager if it's an employee cancelling (not the manager themselves)
                    wa.notify_manager_request_cancelled(
                        manager_phone=mgr_phone,
                        manager_name=team_manager.get('emp_name', 'Manager'),
                        emp_name=emp_info.get('emp_name', f'Employee #{emp_id}'),
                        request_type=req_type_cancelled,
                        request_date=req_date
                    )
        except Exception as wa_err:
            print(f"[WhatsApp] Could not notify manager of cancellation: {wa_err}")
        # ─────────────────────────────────────────────────────────────────

    except Exception as e:
        flash(f'Error cancelling request: {str(e)}', 'danger')
        
    return redirect(request.referrer or url_for('index'))


# ===== ADMIN ROUTES =====

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        emp_name = request.form.get('emp_name')
        password = request.form.get('password')
        
        try:
            # Check manager first, then employee
            user = manager.authenticate_user(emp_name, password, role='admin')
            
            if user:
                session['user_type'] = 'admin'
                session['emp_id'] = user['emp_id']
                session['emp_name'] = user['emp_name']
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials', 'error')
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin-dashboard')
def admin_dashboard():
    """Admin dashboard with notifications"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    
    # Get date for notifications (default to today)
    date_str = request.args.get('date')
    if date_str:
        filter_date = date.fromisoformat(date_str)
    else:
        filter_date = date.today()
    
    # Get notifications for the selected date
    notifications = manager.get_notifications(filter_date=filter_date)
    
    # Get all employees for dropdown
    employees = manager.get_employees()
    
    # Get approval/rejection log for admin
    approval_log = manager.get_approval_log(limit=50)
    
    return render_template('admin_dashboard.html',
                         admin_name=session.get('emp_name'),
                         notifications=notifications,
                         employees=employees,
                         approval_log=approval_log,
                         current_date=filter_date.strftime('%Y-%m-%d'))

@app.route('/admin/performance-report')
def admin_performance_report():
    """View all employees performance report"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    
    # Get all employees with their data
    employees = manager.get_employees()
    
    # Sort by Remaining Leaves (descending) as a default useful view
    # Handle existing NaN/Null values safely
    employees.sort(key=lambda x: x.get('Remaining_Leaves', 0) or 0, reverse=True)
    
    return render_template('admin_performance.html', employees=employees)


@app.route('/admin/view-employee/<int:emp_id>')
def admin_view_employee(emp_id):
    """View specific employee's WFH/Leave records with filtering"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    
    # Get filter parameters
    filter_type = request.args.get('filter_type', 'custom')
    
    today = date.today()
    
    if filter_type == 'monthly':
        month = int(request.args.get('month', today.month))
        year = int(request.args.get('year', today.year))
        start_date = date(year, month, 1)
        # Last day of month
        if month == 12:
            end_date = date(year, 12, 31)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    elif filter_type == 'yearly':
        year = int(request.args.get('year', today.year))
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
    
    else:  # custom
        start_date_str = request.args.get('start_date', (today - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date_str = request.args.get('end_date', today.strftime('%Y-%m-%d'))
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
    
    # Get employee records
    records = manager.get_employee_records(emp_id, start_date, end_date)
    
    # Calculate counts specifically for the returned records
    filtered_wfh_count = sum(1 for r in records if r['type'] == 'WFH')
    filtered_half_day_count = sum(1 for r in records if r['type'] == 'Half Day')
    filtered_leaves_count = sum(1 for r in records if r['type'] == 'Leave')
    
    # Get employee info
    employees = manager.get_employees()
    emp_info = next((e for e in employees if str(e['emp_id']) == str(emp_id)), None)

    # Get rich leave balance info
    leave_balance = manager.get_leave_balance_info(emp_id)
    
    return render_template('admin_view_employee.html',
                         employee=emp_info,
                         leave_balance=leave_balance,
                         records=records,
                         filtered_wfh=filtered_wfh_count,
                         filtered_half_day=filtered_half_day_count,
                         filtered_leaves=filtered_leaves_count,
                         filter_type=filter_type,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'))

@app.route('/logout')
def logout():
    """Logout for both employee and admin"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin/add-employee', methods=['GET', 'POST'])
def add_employee_route():
    """Handle adding new employees"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
        
    if request.method == 'POST':
        try:
            emp_name = request.form.get('emp_name')
            emp_team = request.form.get('emp_team')
            role = request.form.get('role')
            contract_type = request.form.get('contract_type')
            contract_start_date = request.form.get('contract_start_date')
            contract_end_date = request.form.get('contract_end_date')
            
            if contract_type == 'Internship':
                total_leaves = 0
            else:
                total_leaves = int(request.form.get('total_leaves', 14))
            
            if not emp_name or not emp_team:
                flash('Name and Team are required', 'error')
                return redirect(url_for('add_employee_route'))
                
            is_admin = (role == 'admin')
            is_manager = (role == 'manager')
            
            # Use 'SecurePass2026!' as default password
            manager.add_employee(
                emp_name=emp_name,
                emp_team=emp_team,
                is_admin=is_admin,
                is_manager=is_manager,
                contract_type=contract_type,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                total_leaves=total_leaves
            )
            
            return redirect(url_for('admin_dashboard'))
            
        except Exception as e:
            flash(f"Error adding employee: {str(e)}", 'error')
            
    # GET request
    return render_template('admin_add_employee.html', admin_name=session.get('emp_name'))

@app.route('/admin/manage-employees')
def manage_employees_route():
    """List all employees with delete options"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    
    try:
        employees = manager.get_employees()
        return render_template('admin_manage_employees.html', employees=employees)
    except Exception as e:
        flash(f"Error loading employees: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit-employee/<int:emp_id>', methods=['GET', 'POST'])
def edit_employee_route(emp_id):
    """Handle editing existing employees"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
        
    try:
        employees = manager.get_employees()
        employee = next((e for e in employees if str(e['emp_id']) == str(emp_id)), None)
        
        if not employee:
            flash(f"Employee not found", 'error')
            return redirect(url_for('manage_employees_route'))
            
        if request.method == 'POST':
            emp_name = request.form.get('emp_name') or employee.get('emp_name')
            emp_team = request.form.get('emp_team') or employee.get('emp_team')
            role = request.form.get('role')
            
            # Default to existing if role not submitted
            if not role:
                if employee.get('is_admin'): role = 'admin'
                elif employee.get('is_manager'): role = 'manager'
                else: role = 'employee'
                
            contract_type = request.form.get('contract_type') or employee.get('Contract_Type')
            contract_start_date = request.form.get('contract_start_date') or employee.get('Contract_Start_Date')
            contract_end_date = request.form.get('contract_end_date') or employee.get('Contract_End_Date')
            
            raw_leaves = request.form.get('total_leaves')
            raw_carried = request.form.get('carried_forward')
            phone = request.form.get('phone', '').strip()
            
            if contract_type == 'Internship':
                total_leaves = 0
                carried_forward = 0
            else:
                total_leaves = int(raw_leaves) if raw_leaves else employee.get('Total_leaves', 14)
                if pd.isna(total_leaves): total_leaves = 14
                
                carried_forward = float(raw_carried) if raw_carried else employee.get('Leaves_Carried_Forward', 0)
                if pd.isna(carried_forward): carried_forward = 0
            
            is_admin = (role == 'admin')
            is_manager = (role == 'manager')
            
            manager.update_employee(
                emp_id=emp_id,
                emp_name=emp_name,
                emp_team=emp_team,
                is_admin=is_admin,
                is_manager=is_manager,
                contract_type=contract_type,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                total_leaves=total_leaves,
                carried_forward=carried_forward,
                phone=phone
            )
            
            flash(f"Employee {emp_name} updated successfully!", 'success')
            return redirect(url_for('manage_employees_route'))
            
        return render_template('admin_edit_employee.html', employee=employee, admin_name=session.get('emp_name'))
        
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
        return redirect(url_for('manage_employees_route'))

@app.route('/admin/delete-employee/<int:emp_id>', methods=['POST'])
def delete_employee_route(emp_id):
    """Handle employee deletion"""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
        
    try:
        manager.delete_employee(emp_id)
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f"Error deleting employee: {str(e)}", 'error')
        return redirect(url_for('admin_view_employee', emp_id=emp_id))


# ===== WHATSAPP ADMIN ROUTES =====

@app.route('/admin/send-daily-summary', methods=['POST'])
def admin_send_daily_summary():
    """Manually trigger today's daily attendance summary to all managers."""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))

    try:
        _send_daily_summaries()
        flash('✅ Daily attendance summary has been sent to all managers!', 'success')
    except Exception as e:
        flash(f'❌ Error sending daily summary: {str(e)}', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/send-absent-alert', methods=['POST'])
def admin_send_absent_alert():
    """Manually trigger today's absent employee alert to all managers."""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))

    try:
        _send_absent_alerts()
        flash('✅ Absent employee alert has been sent to all managers!', 'success')
    except Exception as e:
        flash(f'❌ Error sending absent alert: {str(e)}', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/whatsapp-settings')
def admin_whatsapp_settings():
    """Show WhatsApp Cloud API configuration status and scheduled jobs."""
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))

    # API status
    token_set = bool(wa.WHATSAPP_ACCESS_TOKEN)
    phone_id_set = bool(wa.WHATSAPP_PHONE_NUMBER_ID)
    enabled = wa.WHATSAPP_ENABLED
    api_version = wa.GRAPH_API_VERSION

    # Managers with phone numbers
    all_managers = manager.get_all_managers()
    managers_with_phone = [m for m in all_managers if m.get('phone') and not pd.isna(m.get('phone')) and str(m.get('phone')).strip()]
    managers_without_phone = [m for m in all_managers if m not in managers_with_phone]

    # Scheduler status
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': str(job.next_run_time) if job.next_run_time else 'Paused',
            'trigger': str(job.trigger)
        })

    return render_template('admin_whatsapp_settings.html',
                           admin_name=session.get('emp_name'),
                           token_set=token_set,
                           phone_id_set=phone_id_set,
                           enabled=enabled,
                           api_version=api_version,
                           managers_with_phone=managers_with_phone,
                           managers_without_phone=managers_without_phone,
                           scheduled_jobs=jobs)



@app.route('/admin/reset-system-balances')
def reset_system_balances():
    """Hidden admin route to reset all balances (Final Initialization)"""
    try:
        import pandas as pd
        file_path = manager.emp_data_file
        df = pd.read_excel(file_path, engine='openpyxl')
        
        # Reset Logic
        results = []
        for idx in df.index:
            name = df.at[idx, 'emp_name']
            c_start = df.at[idx, 'Contract_Start_Date']
            year_start, _ = manager.get_contract_year_window(str(c_start))
            year_start_str = year_start.strftime('%Y-%m-%d') if year_start else ""
            
            df.at[idx, 'Leaves_Carried_Forward'] = 0
            df.at[idx, 'Leaves_This_Year'] = 0
            df.at[idx, 'Leaves'] = 0
            df.at[idx, 'Half_Day'] = 0
            df.at[idx, 'Remaining_Leaves'] = df.at[idx, 'Total_leaves']
            df.at[idx, 'Contract_Year_Start'] = year_start_str
            df.at[idx, 'Carried_Forward_Expiry'] = ""
            results.append(f"{name}: Reset to 14 total, 0 carried. Year Start: {year_start_str}")
            
        df.to_excel(file_path, index=False, engine='openpyxl')
        return "✅ FINAL RESET SUCCESSFUL:<br>" + "<br>".join(results)
    except Exception as e:
        return f"❌ Reset Failed: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)
