from flask import Flask, render_template, request, redirect, url_for, session, flash
from attendance_manager import WFHLeaveManager
from datetime import date, datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Initialize the WFH/Leave manager
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
manager = WFHLeaveManager(BASE_PATH)

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
            user = manager.authenticate_user(emp_name, password, role='employee')
            
            if user:
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
    
    # Get all employees to find current emp data
    employees = manager.get_employees()
    current_emp = next((e for e in employees if str(e['emp_id']) == str(emp_id)), {})
    
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
                         records=records,
                         today=today.strftime('%Y-%m-%d'),
                         filter_type=filter_type,
                         filter_start=start_date.strftime('%Y-%m-%d'),
                         filter_end=end_date.strftime('%Y-%m-%d'))

@app.route('/mark-request', methods=['POST'])
def mark_request():
    """Handle WFH/Leave request from employee"""
    if session.get('user_type') != 'employee':
        return redirect(url_for('employee_login'))
    
    try:
        request_type = request.form.get('request_type')  # 'WFH' or 'Leave' or 'Half Day'
        reason = request.form.get('reason')
        start_date_str = request.form.get('date', date.today().strftime('%Y-%m-%d'))
        end_date_str = request.form.get('end_date') # Optional end date
        
        if not reason or not reason.strip():
            flash('Reason is required', 'error')
            return redirect(url_for('employee_dashboard'))
        
        start_date = date.fromisoformat(start_date_str)
        
        # Determine date range
        if end_date_str and request_type == 'Leave':
            end_date = date.fromisoformat(end_date_str)
            if end_date < start_date:
                flash('End date cannot be before start date', 'error')
                return redirect(url_for('employee_dashboard'))
        else:
            end_date = start_date

        # Iterate through dates
        current_date = start_date
        count = 0
        while current_date <= end_date:
            manager.mark_wfh_leave(
                emp_id=session.get('emp_id'),
                emp_name=session.get('emp_name'),
                emp_team=session.get('emp_team'),
                date=current_date,
                request_type=request_type,
                reason=reason
            )
            current_date += timedelta(days=1)
            count += 1
            
        flash(f'{request_type} request submitted successfully for {count} day(s)!', 'success')
        return redirect(url_for('employee_dashboard'))
        
    except Exception as e:
        flash(f'Error submitting request: {str(e)}', 'error')
        return redirect(url_for('employee_dashboard'))

# ===== ADMIN ROUTES =====

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        emp_name = request.form.get('emp_name')
        password = request.form.get('password')
        
        try:
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
    
    return render_template('admin_dashboard.html',
                         admin_name=session.get('emp_name'),
                         notifications=notifications,
                         employees=employees,
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
    
    # Get employee info
    employees = manager.get_employees()
    emp_info = next((e for e in employees if e['emp_id'] == emp_id), None)
    
    return render_template('admin_view_employee.html',
                         employee=emp_info,
                         records=records,
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
            
            # Use 'SecurePass2026!' as default password
            manager.add_employee(
                emp_name=emp_name,
                emp_team=emp_team,
                is_admin=is_admin,
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
