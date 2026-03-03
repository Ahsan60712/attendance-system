import os
import json
import pandas as pd
from datetime import datetime, date
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment

class WFHLeaveManager:
    def __init__(self, base_path):
        self.base_path = base_path
        excel_filename = os.environ.get('EXCEL_PATH', 'Emp_data.xlsx')
        self.emp_data_file = os.path.join(base_path, excel_filename)
    
    def authenticate_user(self, emp_name, password=None, role='employee'):
        """
        Authenticate user by emp_name and password
        role: 'employee' or 'admin'
        """
        try:
            if not os.path.exists(self.emp_data_file):
                raise FileNotFoundError(f"Employee data file not found: {self.emp_data_file}")
            
            df = pd.read_excel(self.emp_data_file, engine='openpyxl')
            
            # Find employee by name
            emp_row = df[df['emp_name'].str.lower() == emp_name.lower()]
            
            if emp_row.empty:
                return None
            
            emp_data = emp_row.iloc[0].to_dict()
            
            # Verify password if provided (skip check if password column missing for backward compatibility)
            if password and 'password' in emp_data:
                # Convert both to string for comparison to handle Excel number formatting
                if str(emp_data['password']) != str(password):
                    return None
            
            # Check role requirements
            if role == 'admin' and not emp_data.get('is_admin', 0):
                return None
            if role == 'manager' and not emp_data.get('is_manager', 0) and not emp_data.get('is_admin', 0):
                # Admins can also act as managers
                return None
            
            # Return full employee data including counts
            return emp_data
            
        except Exception as e:
            print(f"Error authenticating user: {str(e)}")
            raise Exception(f"Authentication failed. Error: {str(e)}")

    def change_password(self, emp_id, new_password):
        """Update employee password"""
        try:
            df = pd.read_excel(self.emp_data_file, engine='openpyxl')
            
            # Convert emp_id to proper type if needed
            df.loc[df['emp_id'] == emp_id, 'password'] = str(new_password)
            
            df.to_excel(self.emp_data_file, index=False, engine='openpyxl')
            return True
            
        except Exception as e:
            print(f"Error changing password: {str(e)}")
            raise Exception(f"Could not change password. Please ensure Emp_data.xlsx is closed. Error: {str(e)}")
    
    def get_employees(self):
        """Read employee list from Emp_data.xlsx"""
        try:
            if not os.path.exists(self.emp_data_file):
                raise FileNotFoundError(f"Employee data file not found: {self.emp_data_file}")
            
            df = pd.read_excel(self.emp_data_file, engine='openpyxl')
            return df.to_dict('records')
        except Exception as e:
            print(f"Error reading employee data: {str(e)}")
            raise Exception(f"Could not read employee data. Please ensure Emp_data.xlsx is closed in Excel and is a valid Excel file. Error: {str(e)}")
    
    def get_daily_filepath(self, date_obj, create_dir=False):
        """Construct path: base_path/YYYY/Month/dd-mon-yyyy.xlsx"""
        year = date_obj.strftime('%Y')
        month = date_obj.strftime('%B') # Full month name
        filename = date_obj.strftime('%d-%b-%Y').lower() + '.xlsx'
        
        folder_path = os.path.join(self.base_path, year, month)
        
        if create_dir and not os.path.exists(folder_path):
            os.makedirs(folder_path)
            
        return os.path.join(folder_path, filename)
    
    def mark_wfh_leave(self, emp_id, emp_name, emp_team, date, request_type, reason, status='Pending', manager_name=''):
        """
        Mark WFH or Leave for an employee
        request_type: 'WFH' or 'Leave'
        reason: mandatory text explaining the request
        status: 'Pending' or 'Approved'
        manager_name: Name of manager if auto-approved
        """
        # Get structured filepath
        workbook_path = self.get_daily_filepath(date, create_dir=True)
        
        # Delete existing file if it exists (to ensure fresh data)
        # REMOVED: This was deleting the file and causing previous entries to be lost
        # We will instead load the workbook if it exists
        
        # Get all employees
        employees = self.get_employees()
        
        if os.path.exists(workbook_path):
            wb = load_workbook(workbook_path)
            ws = wb.active
            # Fix: If old file has no Status/Action By headers, add them now
            if ws.cell(row=1, column=7).value is None:
                ws.cell(row=1, column=7, value='Status')
                ws.cell(row=1, column=8, value='Action By')
                # Backfill existing data rows with Pending status
                for r in range(2, ws.max_row + 1):
                    if ws.cell(row=r, column=1).value and ws.cell(row=r, column=7).value is None:
                        ws.cell(row=r, column=7, value='Pending')
                        ws.cell(row=r, column=8, value='')
        else:
            # Create new workbook
            wb = Workbook()
            ws = wb.active
            ws.title = date.strftime('%d-%b-%Y').lower()
            
            # Header styling
            header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            header_font = Font(bold=True, color='FFFFFF', size=12)
            
            # Headers with Approval Status
            headers = ['Emp ID', 'Employee Name', 'Team', 'Request Type', 'Reason', 'Timestamp', 'Status', 'Action By']
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')

        # Find the next available row
        next_row = ws.max_row + 1

        # Add only the employee's request
        ws.cell(row=next_row, column=1, value=emp_id)
        ws.cell(row=next_row, column=2, value=emp_name)
        ws.cell(row=next_row, column=3, value=emp_team)
        
        # Request type with color coding
        type_cell = ws.cell(row=next_row, column=4, value=request_type)
        if request_type == 'WFH':
            type_cell.fill = PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid')
            type_cell.font = Font(color='9C6500')
        elif request_type == 'Leave':
            type_cell.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
            type_cell.font = Font(color='9C0006')
        elif request_type == 'Half Day':
            type_cell.fill = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')
            type_cell.font = Font(color='38761D')
            
        type_cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Reason, Timestamp, Status
        ws.cell(row=next_row, column=5, value=reason)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ws.cell(row=next_row, column=6, value=timestamp)
        ws.cell(row=next_row, column=7, value=status)
        ws.cell(row=next_row, column=8, value=manager_name if status == 'Approved' else '')
        
        # Auto-adjust column widths
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 25
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 40
        ws.column_dimensions['F'].width = 20
        
        # Save workbook
        wb.save(workbook_path)
        
        # If auto-approved (manager case), update counters and log for admin immediately
        if status == 'Approved':
            self.update_employee_counters(emp_id, request_type)
            self.log_approval_action(
                emp_id=emp_id,
                emp_name=emp_name,
                request_type=request_type,
                request_date=date.strftime('%Y-%m-%d'),
                status='Approved',
                manager_name=manager_name or emp_name
            )
        
        return True
    
    def update_employee_counters(self, emp_id, request_type):
        """Update WFH_count, Leaves, or Half_Day counter in Emp_data.xlsx"""
        try:
            df = pd.read_excel(self.emp_data_file, engine='openpyxl')
            
            emp_row = df[df['emp_id'] == emp_id]
            if emp_row.empty:
                return
            
            idx = emp_row.index[0]
            
            if request_type == 'WFH':
                df.at[idx, 'WFH_count'] = df.at[idx, 'WFH_count'] + 1 if pd.notna(df.at[idx, 'WFH_count']) else 1
            elif request_type == 'Leave':
                if pd.notna(df.at[idx, 'Remaining_Leaves']) and df.at[idx, 'Remaining_Leaves'] < 1:
                    raise Exception("Insufficient remaining leaves")
                df.at[idx, 'Leaves'] = df.at[idx, 'Leaves'] + 1 if pd.notna(df.at[idx, 'Leaves']) else 1
                if pd.notna(df.at[idx, 'Remaining_Leaves']):
                    df.at[idx, 'Remaining_Leaves'] = df.at[idx, 'Remaining_Leaves'] - 1
            elif request_type == 'Half Day':
                if pd.notna(df.at[idx, 'Remaining_Leaves']) and df.at[idx, 'Remaining_Leaves'] < 0.5:
                    raise Exception("Insufficient remaining leaves for a half day")
                df.at[idx, 'Half_Day'] = df.at[idx, 'Half_Day'] + 1 if pd.notna(df.at[idx, 'Half_Day']) else 1
                if pd.notna(df.at[idx, 'Remaining_Leaves']):
                    # Half day reduces remaining leaves by 0.5
                    df.at[idx, 'Remaining_Leaves'] = df.at[idx, 'Remaining_Leaves'] - 0.5
            
            df.to_excel(self.emp_data_file, index=False, engine='openpyxl')
            
        except Exception as e:
            print(f"Error updating employee counters: {str(e)}")
            raise Exception(f"Could not update Emp_data.xlsx. Please ensure it is closed in Excel. Error: {str(e)}")
    

    def get_notifications(self, filter_date=None, limit=None):
        """
        Get WFH/Leave requests for a specific date (default: today)
        If limit is provided, it's ignored in this new date-based logic 
        (we show all requests for the day)
        """
        notifications = []
        
        try:
            if filter_date is None:
                filter_date = date.today()
            
            # Use helper to get structured path
            filepath = self.get_daily_filepath(filter_date)
            
            if os.path.exists(filepath):
                try:
                    wb = load_workbook(filepath, data_only=True)
                    ws = wb.active
                    
                    # Read each row (skip header)
                    for row_num in range(2, ws.max_row + 1):
                        emp_id = ws.cell(row=row_num, column=1).value
                        emp_name = ws.cell(row=row_num, column=2).value
                        team = ws.cell(row=row_num, column=3).value
                        request_type = ws.cell(row=row_num, column=4).value
                        reason = ws.cell(row=row_num, column=5).value
                        timestamp = ws.cell(row=row_num, column=6).value
                        status = ws.cell(row=row_num, column=7).value
                        
                        # Set default status for older files without the status column
                        if status is None:
                            status = 'Approved' 
                            
                        if emp_id:
                            notifications.append({
                                'date': filter_date.strftime('%d-%b-%Y'),
                                'emp_id': emp_id,
                                'emp_name': emp_name,
                                'team': team,
                                'type': request_type,
                                'reason': reason,
                                'timestamp': timestamp,
                                'status': status
                            })
                            
                    # Reverse to show newest first for that day
                    notifications.reverse()
                    
                except Exception as e:
                    print(f"Error reading notification file {filepath}: {str(e)}")
            
            return notifications
            
        except Exception as e:
            print(f"Error getting notifications: {str(e)}")
            return []

    def get_pending_requests(self, days_back=30):
        """Scan recent daily files for any 'Pending' requests"""
        pending = []
        try:
            from datetime import timedelta
            end_date = date.today()
            start_date = end_date - timedelta(days=days_back)
            
            current_date = start_date
            while current_date <= end_date:
                filepath = self.get_daily_filepath(current_date)
                
                if os.path.exists(filepath):
                    try:
                        wb = load_workbook(filepath, data_only=True)
                        ws = wb.active
                        
                        for row_num in range(2, ws.max_row + 1):
                            emp_id = ws.cell(row=row_num, column=1).value
                            if not emp_id:
                                continue
                            status = ws.cell(row=row_num, column=7).value
                            # Treat None (legacy rows without status column) as Pending
                            if status in ('Pending', None):
                                emp_name = ws.cell(row=row_num, column=2).value
                                request_type = ws.cell(row=row_num, column=4).value
                                reason = ws.cell(row=row_num, column=5).value
                                timestamp = ws.cell(row=row_num, column=6).value
                                
                                pending.append({
                                    'date': current_date.strftime('%Y-%m-%d'),
                                    'display_date': current_date.strftime('%d-%b-%Y'),
                                    'emp_id': emp_id,
                                    'emp_name': emp_name,
                                    'type': request_type,
                                    'reason': reason,
                                    'timestamp': timestamp
                                })
                    except Exception as e:
                        print(f"Error reading {filepath}: {str(e)}")
                
                current_date += timedelta(days=1)
                
            # Sort newest first
            pending.sort(key=lambda x: x['timestamp'], reverse=True)
            return pending
            
        except Exception as e:
            print(f"Error getting pending requests: {str(e)}")
            return []
            
    def update_request_status(self, request_date_str, emp_id, request_type, timestamp, new_status, manager_name):
        """Update a specific request from Pending to Approved or Rejected"""
        try:
            req_date = datetime.strptime(request_date_str, '%Y-%m-%d').date()
            filepath = self.get_daily_filepath(req_date)
            
            if not os.path.exists(filepath):
                raise Exception(f"File not found for date: {request_date_str}")
                
            wb = load_workbook(filepath)
            ws = wb.active
            
            updated = False
            emp_name_found = ''
            for row_num in range(2, ws.max_row + 1):
                file_emp_id = ws.cell(row=row_num, column=1).value
                file_timestamp = ws.cell(row=row_num, column=6).value
                
                # Match exactly the right row using employee ID and their unique timestamp
                if str(file_emp_id) == str(emp_id) and str(file_timestamp) == str(timestamp):
                    emp_name_found = ws.cell(row=row_num, column=2).value or ''
                    ws.cell(row=row_num, column=7, value=new_status)
                    ws.cell(row=row_num, column=8, value=manager_name)
                    updated = True
                    break
                    
            if not updated:
                raise Exception("Could not find the specific request to update.")
                
            wb.save(filepath)
            
            # If approved, deduct from employee counters
            if new_status == 'Approved':
                self.update_employee_counters(emp_id, request_type)
            
            # Log the action for admin notifications
            self.log_approval_action(
                emp_id=emp_id,
                emp_name=emp_name_found,
                request_type=request_type,
                request_date=request_date_str,
                status=new_status,
                manager_name=manager_name
            )
                
            return True
        except Exception as e:
            print(f"Error updating request status: {str(e)}")
            raise Exception(f"Failed to update status: {str(e)}")

    def log_approval_action(self, emp_id, emp_name, request_type, request_date, status, manager_name):
        """Append an approved/rejected action entry to approved_log.json"""
        log_path = os.path.join(self.base_path, 'approved_log.json')
        try:
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    log = json.load(f)
            else:
                log = []
            
            log.insert(0, {
                'emp_id': emp_id,
                'emp_name': emp_name,
                'request_type': request_type,
                'request_date': request_date,
                'status': status,
                'manager_name': manager_name,
                'actioned_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            # Keep only the latest 200 entries
            log = log[:200]
            
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log, f, indent=2)
        except Exception as e:
            print(f"Error writing approval log: {str(e)}")

    def get_approval_log(self, limit=50):
        """Return recent approved/rejected actions for admin notifications"""
        log_path = os.path.join(self.base_path, 'approved_log.json')
        try:
            if not os.path.exists(log_path):
                return []
            with open(log_path, 'r', encoding='utf-8') as f:
                log = json.load(f)
            return log[:limit]
        except Exception as e:
            print(f"Error reading approval log: {str(e)}")
            return []

    def get_employee_records(self, emp_id, start_date, end_date):
        """Get all WFH/Leave records for an employee within date range"""
        records = []
        
        try:
            current_date = start_date
            while current_date <= end_date:
                # Use helper to get structured path
                filepath = self.get_daily_filepath(current_date)
                
                if os.path.exists(filepath):
                    try:
                        wb = load_workbook(filepath, data_only=True)
                        ws = wb.active
                        
                        for row_num in range(2, ws.max_row + 1):
                            file_emp_id = ws.cell(row=row_num, column=1).value
                            
                            # Determine if this row belongs to the employee
                            if str(file_emp_id) == str(emp_id):
                                status = ws.cell(row=row_num, column=7).value
                                if status is None:
                                    status = 'Approved' # Legacy default
                                    
                                records.append({
                                    'date': current_date.strftime('%d-%b-%Y'),
                                    'type': ws.cell(row=row_num, column=4).value,
                                    'reason': ws.cell(row=row_num, column=5).value,
                                    'timestamp': ws.cell(row=row_num, column=6).value,
                                    'status': status
                                })
                    except:
                        pass
                
                # Move to next day
                from datetime import timedelta
                current_date += timedelta(days=1)
            
            return records
            
        except Exception as e:
            print(f"Error getting employee records: {str(e)}")
            return []

    def add_employee(self, emp_name, emp_team, is_admin, is_manager, contract_type, contract_start_date, contract_end_date, total_leaves, password='SecurePass2026!'):
        """Add a new employee to Emp_data.xlsx"""
        try:
            if not os.path.exists(self.emp_data_file):
                raise FileNotFoundError("Employee data file not found")
            
            df = pd.read_excel(self.emp_data_file, engine='openpyxl')
            
            # Generate new emp_id (max + 1)
            new_id = df['emp_id'].max() + 1 if not df.empty else 1
            
            new_emp = {
                'emp_id': new_id,
                'emp_name': emp_name,
                'emp_team': emp_team,
                'Total_leaves': total_leaves,
                'Half_Day': 0,
                'Leaves': 0,
                'Present': 0,
                'Remaining_Leaves': total_leaves,
                'is_admin': 1 if is_admin else 0,
                'is_manager': 1 if is_manager else 0,
                'WFH_count': 0,
                'password': password,
                'Contract_Type': contract_type,
                'Contract_Start_Date': contract_start_date,
                'Contract_End_Date': contract_end_date
            }
            
            # Append new row
            df = pd.concat([df, pd.DataFrame([new_emp])], ignore_index=True)
            
            df.to_excel(self.emp_data_file, index=False, engine='openpyxl')
            return new_id
            
        except Exception as e:
            print(f"Error adding employee: {str(e)}")
            raise Exception(f"Could not add employee: {str(e)}")

    def delete_employee(self, emp_id):
        """Delete an employee from Emp_data.xlsx"""
        try:
            if not os.path.exists(self.emp_data_file):
                raise FileNotFoundError("Employee data file not found")
            
            df = pd.read_excel(self.emp_data_file, engine='openpyxl')
            
            # Remove employee row
            df = df[df['emp_id'] != int(emp_id)]
            
            df.to_excel(self.emp_data_file, index=False, engine='openpyxl')
            return True
            
        except Exception as e:
            print(f"Error deleting employee: {str(e)}")
            raise Exception(f"Could not delete employee: {str(e)}")
