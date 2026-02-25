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

if __name__ == "__main__":
    try:
        test_admin_dashboard_date_filter()
        print("Test Complete")
    except Exception as e:
        print(f"Test Failed: {e}")
