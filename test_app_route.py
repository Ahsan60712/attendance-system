from app import app
from datetime import date
from datetime import date

def test_admin_dashboard_date_filter():
    with app.test_client() as client:
        # Mock session
        with client.session_transaction() as sess:
            sess['user_type'] = 'admin'
            sess['emp_name'] = 'Admin User'
            sess['emp_id'] = 999 
        
        # Test Default (Today)
        response = client.get('/admin-dashboard')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        print(f"Default View Content Length: {len(content)}")
        today_str = date.today().strftime('%Y-%m-%d')
        if today_str in content:
            print("✅ Default view contains today's date")
        else:
            print("❌ Default view MISSING today's date")

        # Test Specific Date (20-Jan-2026)
        response = client.get('/admin-dashboard?date=2026-01-20')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        if '2026-01-20' in content:
             print("✅ Specific date query param reflected in page")
        
        # Check if notifications are present (we know there is one for 20-jan)
        # The notification html usually has the employee name "Muhammad Ahsan"
        if 'Muhammad Ahsan' in content:
             print("✅ Found 'Muhammad Ahsan' in 20-Jan View (Notification present)")
        else:
             print("❌ 'Muhammad Ahsan' NOT found in 20-Jan View")

def test_ceo_dashboard():
    with app.test_client() as client:
        # Mock session
        with client.session_transaction() as sess:
            sess['user_type'] = 'ceo'
            sess['emp_name'] = 'CEO User'
            sess['emp_id'] = 17 # CEO Najm is ID 17
        
        response = client.get('/ceo-dashboard')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        print(f"CEO View Content Length: {len(content)}")
        if 'Employees Leave Directory' in content:
             print("✅ CEO dashboard contains Employees Leave Directory tab")
        else:
             print("❌ CEO dashboard MISSING Employees Leave Directory tab")

def test_export_beyond_schedule():
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_type'] = 'admin'
            sess['emp_name'] = 'Admin User'
            sess['emp_id'] = 999
        
        response = client.get('/export-beyond-schedule')
        assert response.status_code == 200
        assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        print("✅ Beyond Schedule Export to Excel route works successfully")

def test_view_beyond_schedule():
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_type'] = 'admin'
            sess['emp_name'] = 'Admin User'
            sess['emp_id'] = 999
        
        response = client.get('/view-beyond-schedule')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        print(f"Beyond Schedule Grid View Content Length: {len(content)}")
        assert 'Beyond Schedule Grid' in content
        assert 'Off Day' in content
        print("✅ Beyond Schedule View loads and displays 'Off Day' successfully")

def test_manager_dashboard():
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_type'] = 'manager'
            sess['emp_name'] = 'Hafiz Zohaib'
            sess['emp_id'] = 5
            sess['emp_team'] = 'Overstock'
            
        response = client.get('/manager-dashboard')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        print(f"Manager Dashboard Content Length: {len(content)}")
        assert 'Beyond Schedule Grid' in content
        assert 'Monday' in content
        assert 'Tuesday' in content
        print("✅ Manager dashboard loads and displays Beyond Schedule tab successfully")

if __name__ == "__main__":
    import sys
    try:
        test_admin_dashboard_date_filter()
        test_ceo_dashboard()
        test_export_beyond_schedule()
        test_view_beyond_schedule()
        test_manager_dashboard()
        print("Tests Complete")
        sys.exit(0)
    except Exception as e:
        print(f"Test Failed: {e}")
        sys.exit(1)
