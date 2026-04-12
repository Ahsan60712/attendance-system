"""
WhatsApp Notification Module — Meta WhatsApp Cloud API (Official)
================================================================

Uses the official Meta Graph API to send WhatsApp messages.
No Twilio dependency — just the `requests` library.

Setup:
  1. Go to https://developers.facebook.com → Create an app → Add WhatsApp product
  2. Go to WhatsApp → API Setup:
     - Copy the "Phone number ID"
     - Copy the temporary or permanent "Access Token"
  3. Set environment variables (see .env.example)
  4. Add manager phone numbers with country code in Emp_data.xlsx

Notification Events:
  - Employee submits a new request   → notify their team manager
  - Manager approves / rejects       → notify the employee
  - Employee cancels a request       → notify the team manager
  - Daily attendance summary         → notify all managers
  - Absent employee alert            → notify team managers
"""

import os
import logging
import requests
from datetime import date

logger = logging.getLogger(__name__)

# ── Meta WhatsApp Cloud API credentials ───────────────────────────────────────
# Get these from https://developers.facebook.com → Your App → WhatsApp → API Setup
WHATSAPP_ACCESS_TOKEN   = os.environ.get('WHATSAPP_ACCESS_TOKEN', 'EAAhAoaIn5A0BRBzZBkX3xZB8CbMMqfxLvrRPG2plFhjjLblIy2u9KcxdQ5vz1Fr6NIdEt1iZARBR4Hp7poNpqnAW4E7K8n58tNSnLViOv4w2ZAWTItY2sMMOsOc2og3YBKZCvZAj6VbD2qeuPMGygUG8x2FdbP7mHeMLydRnafcMLhB01TrFBdell9MLCu5ZBxl1wZDZD')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '1042667845599788')

# Graph API version
GRAPH_API_VERSION = os.environ.get('GRAPH_API_VERSION', 'v25.0')

# Set to True to actually send messages; False = dry-run (logged only)
WHATSAPP_ENABLED = os.environ.get('WHATSAPP_ENABLED', 'true').lower() == 'true'

# Build the API URL
API_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"


def _format_phone(phone: str) -> str:
    """
    Ensure phone number is in E.164 format WITHOUT the '+' prefix
    (Meta API expects digits only, e.g. '923001234567').

    Accepts: '03001234567', '+923001234567', '923001234567', 'whatsapp:+923001234567'
    Returns: '923001234567'
    """
    phone = str(phone).strip().replace(' ', '').replace('-', '')
    if not phone:
        return ''

    # Strip any old Twilio-style prefix if present
    phone = phone.replace('whatsapp:', '')

    # Strip leading +
    phone = phone.lstrip('+')

    # Convert Pakistani local format (03xx → 923xx)
    if phone.startswith('0') and len(phone) == 11:
        phone = '92' + phone[1:]

    return phone


def send_whatsapp(to_phone: str, message: str) -> bool:
    """
    Send a WhatsApp text message via Meta Cloud API.

    Args:
        to_phone: Recipient phone (any reasonable format; see _format_phone).
        message:  Plain-text message body.

    Returns:
        True on success (or dry-run), False on failure.
    """
    recipient = _format_phone(to_phone)
    if not recipient:
        logger.warning("[WhatsApp] Skipped: empty or invalid phone number.")
        return False

    # Always log the message for auditing
    logger.info(f"[WhatsApp] → {recipient}: {message[:80]}...")

    if not WHATSAPP_ENABLED:
        print(f"[WhatsApp DRY-RUN] To: {recipient}\n{message}\n")
        return True

    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print(f"[WhatsApp SKIP] Credentials not set. Would send to {recipient}:\n{message}\n")
        return False

    headers = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }

    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': recipient,
        'type': 'text',
        'text': {
            'preview_url': False,
            'body': message
        }
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            msg_id = data.get('messages', [{}])[0].get('id', 'N/A')
            logger.info(f"[WhatsApp] ✅ Sent to {recipient} | ID: {msg_id}")
            print(f"[WhatsApp] ✅ Sent to {recipient} | ID: {msg_id}")
            return True
        else:
            error_data = response.json().get('error', {})
            error_msg = error_data.get('message', response.text[:200])
            logger.error(f"[WhatsApp] ❌ API Error ({response.status_code}): {error_msg}")
            print(f"[WhatsApp] ❌ API Error ({response.status_code}): {error_msg}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"[WhatsApp] ❌ Timeout sending to {recipient}")
        print(f"[WhatsApp] ❌ Timeout sending to {recipient}")
        return False
    except Exception as e:
        logger.error(f"[WhatsApp] ❌ Failed to send to {recipient}: {e}")
        print(f"[WhatsApp] ❌ Failed to send to {recipient}: {e}")
        return False


def send_whatsapp_template(to_phone: str, template_name: str, language_code: str, components: list) -> bool:
    """
    Send a template-based WhatsApp message via Meta Cloud API.
    """
    recipient = _format_phone(to_phone)
    if not recipient:
        return False

    if not WHATSAPP_ENABLED:
        print(f"[WhatsApp DRY-RUN] Template: {template_name} to {recipient}")
        return True

    headers = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
    }

    payload = {
        'messaging_product': 'whatsapp',
        'to': recipient,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {
                'code': language_code
            },
            'components': components
        }
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            print(f"[WhatsApp Template] ✅ Sent {template_name} to {recipient}")
            return True
        else:
            print(f"[WhatsApp Template] ❌ API Error ({response.status_code}): {response.text}")
            logger.error(f"[WhatsApp Template] API Error: {response.text}")
            return False
    except Exception as e:
        print(f"[WhatsApp Template] ❌ Exception: {e}")
        return False


# ── High-level notification helpers ──────────────────────────────────────────

def notify_manager_new_request(manager_phone: str, manager_name: str,
                                 emp_name: str, request_type: str,
                                 request_date: str, reason: str) -> bool:
    """
    Notify a manager that an employee has submitted a new leave/WFH request.
    Uses THE 'leave_request_notification' template.
    Variable {{1}} = Employee Name
    Variable {{2}} = request_type / reason
    """
    # Override for testing: Hafiz Zohaib (03441292307)
    test_num = os.environ.get('TEST_MANAGER_PHONE', '03441292307')
    target_phone = test_num if test_num else manager_phone

    components = [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": emp_name},
                {"type": "text", "text": request_type} # Variable {{2}} = WFH / Leave / Half Day
            ]
        }
    ]
    
    return send_whatsapp_template(
        to_phone=target_phone,
        template_name="leave_request_notification",
        language_code="en",
        components=components
    )


def notify_employee_request_submitted(emp_phone: str, emp_name: str,
                                       request_type: str, request_date: str) -> bool:
    """
    Notify an employee that their request has been successfully submitted.
    """
    message = (
        f"📝 *Request Submitted*\n\n"
        f"Hi {emp_name},\n"
        f"Your *{request_type}* request for *{request_date}* has been "
        f"successfully submitted and is pending manager approval.\n\n"
        f"You will be notified once a decision is made."
    )
    return send_whatsapp(emp_phone, message)



def notify_employee_decision(emp_phone: str, emp_name: str, manager_name: str,
                              request_type: str, request_date: str,
                              decision: str) -> bool:
    """
    Notify an employee that their request has been approved or rejected.
    """
    icon = '✅' if decision == 'Approved' else '❌'
    message = (
        f"{icon} *Request {decision}*\n\n"
        f"Hi {emp_name},\n"
        f"Your *{request_type}* request for *{request_date}* has been "
        f"*{decision}* by {manager_name}.\n\n"
        f"Please check the Attendance System for details."
    )
    return send_whatsapp(emp_phone, message)


def notify_manager_request_cancelled(manager_phone: str, manager_name: str,
                                       emp_name: str, request_type: str,
                                       request_date: str) -> bool:
    """
    Notify a manager that an employee has cancelled a request.
    """
    message = (
        f"🚫 *Request Cancelled*\n\n"
        f"Hi {manager_name},\n"
        f"*{emp_name}* has cancelled their *{request_type}* request "
        f"for *{request_date}*."
    )
    return send_whatsapp(manager_phone, message)


# ── Daily Summary & Absent Alerts ────────────────────────────────────────────

def send_daily_summary(manager_phone: str, manager_name: str,
                        summary_date: date, team_name: str,
                        wfh_list: list, leave_list: list,
                        half_day_list: list, absent_list: list) -> bool:
    """
    Send a daily attendance summary to a manager.

    Args:
        wfh_list:     List of employee names working from home.
        leave_list:   List of employee names on leave.
        half_day_list: List of employee names on half day.
        absent_list:  List of employee names absent (no request filed).
    """
    date_str = summary_date.strftime('%d %b %Y (%A)')

    lines = [
        f"📊 *Daily Attendance Summary*",
        f"📅 *Date:* {date_str}",
        f"👥 *Team:* {team_name}",
        f"",
    ]

    if wfh_list:
        lines.append(f"🏠 *WFH ({len(wfh_list)}):*")
        for name in wfh_list:
            lines.append(f"  • {name}")
        lines.append("")

    if leave_list:
        lines.append(f"🏖️ *On Leave ({len(leave_list)}):*")
        for name in leave_list:
            lines.append(f"  • {name}")
        lines.append("")

    if half_day_list:
        lines.append(f"⏰ *Half Day ({len(half_day_list)}):*")
        for name in half_day_list:
            lines.append(f"  • {name}")
        lines.append("")

    if absent_list:
        lines.append(f"⚠️ *No Request Filed ({len(absent_list)}):*")
        for name in absent_list:
            lines.append(f"  • {name}")
        lines.append("")

    if not wfh_list and not leave_list and not half_day_list and not absent_list:
        lines.append("✅ All team members are present in office today!")

    total_away = len(wfh_list) + len(leave_list) + len(half_day_list)
    lines.append(f"📈 *Total Away:* {total_away} | *Unaccounted:* {len(absent_list)}")

    message = "\n".join(lines)
    return send_whatsapp(manager_phone, message)


def send_absent_alert(manager_phone: str, manager_name: str,
                       absent_employees: list, team_name: str,
                       alert_date: date) -> bool:
    """
    Alert a manager about employees who have no request filed for today.
    """
    if not absent_employees:
        return True  # Nothing to alert

    date_str = alert_date.strftime('%d %b %Y')
    names = "\n".join(f"  • {name}" for name in absent_employees)

    message = (
        f"⚠️ *Absent Employee Alert*\n\n"
        f"📅 *Date:* {date_str}\n"
        f"👥 *Team:* {team_name}\n\n"
        f"The following employees have *no request filed* "
        f"and may be absent:\n\n"
        f"{names}\n\n"
        f"Please check with them or mark attendance accordingly."
    )
    return send_whatsapp(manager_phone, message)


def notify_employee_absence(emp_phone: str, emp_name: str, alert_date: date) -> bool:
    """
    Directly notify an employee that they have no request filed for today.
    """
    date_str = alert_date.strftime('%d %b %Y')
    message = (
        f"⚠️ *Attendance Alert*\n\n"
        f"Hi {emp_name},\n"
        f"We noticed that you have *no request filed* (Leave/WFH) for today, "
        f"*{date_str}*.\n\n"
        f"Please log in to the Attendance System to mark your status if you are away."
    )
    return send_whatsapp(emp_phone, message)
