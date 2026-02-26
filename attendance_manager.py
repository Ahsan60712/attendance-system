import os
import pandas as pd
from datetime import datetime, date
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment

class WFHLeaveManager:
    def __init__(self, base_path):
        self.base_path = base_path
        # Use environment variable for the file path if available, otherwise default to local 'Emp_data.xlsx'
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
            
            # Check if admin access is required
            if role == 'admin':
                if not emp_data.get('is_admin', 0):
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
    
    def mark_wfh_leave(self, emp_id, emp_name, emp_team, date, request_type, reason):
        """
        Mark WFH or Leave for an employee
        request_type: 'WFH' or 'Leave'
        reason: mandatory text explaining the request
        """
        # Get structured filepath
        workbook_path = self.get_daily_filepath(date, create_dir=True)
        
        # Delete existing file if it exists (to ensure fresh data)
        if os.path.exists(workbook_path):
            try:
                os.remove(workbook_path)
            except Exception as e:
                # Try to get just the filename for the error message
                fname = os.path.basename(workbook_path)
                raise Exception(f"Could not delete existing file {fname}. Please close it in Excel first. Error: {str(e)}")
        
        # Get all employees
        employees = self.get_employees()
        
        # Create new workbook
        wb = Workbook()
        ws = wb.active
        ws.title = date.strftime('%d-%b-%Y').lower()
        
        # Header styling
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF', size=12)
        
        # Headers
        headers = ['Emp ID', 'Employee Name', 'Team', 'Request Type', 'Reason', 'Timestamp']
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Add only the employee's request
        ws.cell(row=2, column=1, value=emp_id)
        ws.cell(row=2, column=2, value=emp_name)
        ws.cell(row=2, column=3, value=emp_team)
        
        # Request type with color coding
        type_cell = ws.cell(row=2, column=4, value=request_type)
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
        
        # Reason
        ws.cell(row=2, column=5, value=reason)
        
        # Timestamp
        ws.cell(row=2, column=6, value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Auto-adjust column widths
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 25
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 40
        ws.column_dimensions['F'].width = 20
        
        # Save workbook
        wb.save(workbook_path)
        
        # Update Emp_data.xlsx counters
        self.update_employee_counters(emp_id, request_type)
        
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
                df.at[idx, 'Leaves'] = df.at[idx, 'Leaves'] + 1 if pd.notna(df.at[idx, 'Leaves']) else 1
                if pd.notna(df.at[idx, 'Remaining_Leaves']):
                    df.at[idx, 'Remaining_Leaves'] = df.at[idx, 'Remaining_Leaves'] - 1
            elif request_type == 'Half Day':
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
                        
                        if emp_id:
                            notifications.append({
                                'date': filter_date.strftime('%d-%b-%Y'),
                                'emp_id': emp_id,
                                'emp_name': emp_name,
                                'team': team,
                                'type': request_type,
                                'reason': reason,
                                'timestamp': timestamp
                            })
                            
                    # Reverse to show newest first for that day
                    notifications.reverse()
                    
                except Exception as e:
                    print(f"Error reading notification file {filepath}: {str(e)}")
            
            return notifications
            
        except Exception as e:
            print(f"Error getting notifications: {str(e)}")
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
                            
                            # Determine if this row belongs to the employee (handle int vs str mismatch)
                            if str(file_emp_id) == str(emp_id):
                                records.append({
                                    'date': current_date.strftime('%d-%b-%Y'),
                                    'type': ws.cell(row=row_num, column=4).value,
                                    'reason': ws.cell(row=row_num, column=5).value,
                                    'timestamp': ws.cell(row=row_num, column=6).value
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

    def add_employee(self, emp_name, emp_team, is_admin, contract_type, contract_start_date, contract_end_date, total_leaves, password='SecurePass2026!'):
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
