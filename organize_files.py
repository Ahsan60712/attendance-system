import os
import shutil
from datetime import datetime
import glob

def organize_files():
    base_path = os.getcwd()
    print(f"Scanning {base_path} for Excel files...")
    
    # helper to get month name
    def get_month_name(month_num):
        return datetime(2000, month_num, 1).strftime('%B')

    # Find all daily excel files (pattern: dd-mon-yyyy.xlsx)
    # Using a simple logic: filename matches format 
    
    count = 0
    errors = 0
    
    for file in os.listdir(base_path):
        if file.endswith('.xlsx') and file != 'Emp_data.xlsx':
            try:
                # Parse date from filename (e.g., 21-jan-2026.xlsx)
                date_str = file.replace('.xlsx', '')
                date_obj = datetime.strptime(date_str, '%d-%b-%Y')
                
                year = date_obj.strftime('%Y')
                month = date_obj.strftime('%B')
                
                # Create directory structure
                target_dir = os.path.join(base_path, year, month)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                    print(f"Created directory: {target_dir}")
                
                # Move file
                src_path = os.path.join(base_path, file)
                dst_path = os.path.join(target_dir, file)
                
                shutil.move(src_path, dst_path)
                print(f"Moved {file} -> {year}/{month}/{file}")
                count += 1
                
            except ValueError:
                # Not a daily file (could be something else)
                print(f"Skipping {file} (not a daily record)")
                continue
            except Exception as e:
                print(f"Error moving {file}: {e}")
                errors += 1

    print(f"\nMigration Complete.")
    print(f"Files moved: {count}")
    print(f"Errors: {errors}")

if __name__ == '__main__':
    organize_files()
