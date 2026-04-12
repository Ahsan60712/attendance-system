
import whatsapp_notifier as wa

# Test the actual module function
success = wa.notify_manager_new_request(
    manager_phone="03441292307",
    manager_name="Hafiz Zohaib",
    emp_name="Test Employee",
    request_type="Leave",
    request_date="12-Apr-2026",
    reason="Testing API Integration"
)

if success:
    print("✅ Module call successful. Message should be sent to 03441292307.")
else:
    print("❌ Module call failed.")
