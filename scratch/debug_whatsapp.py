
import os
import requests
import json

# Manual settings for debugging based on user request
ACCESS_TOKEN = "EAAhAoaIn5A0BRBzZBkX3xZB8CbMMqfxLvrRPG2plFhjjLblIy2u9KcxdQ5vz1Fr6NIdEt1iZARBR4Hp7poNpqnAW4E7K8n58tNSnLViOv4w2ZAWTItY2sMMOsOc2og3YBKZCvZAj6VbD2qeuPMGygUG8x2FdbP7mHeMLydRnafcMLhB01TrFBdell9MLCu5ZBxl1wZDZD"
PHONE_NUMBER_ID = "1042667845599788"
RECIPIENT_PHONE = "03441292307"
TEMPLATE_NAME = "leave_request_notification"

# Format phone (Pakistani local to International)
def format_phone(p):
    p = p.strip().replace(' ', '').replace('-', '').replace('+', '')
    if p.startswith('0') and len(p) == 11:
        p = '92' + p[1:]
    return p

recipient = format_phone(RECIPIENT_PHONE)
url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"

headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json',
}

payload = {
    'messaging_product': 'whatsapp',
    'recipient_type': 'individual',
    'to': recipient,
    'type': 'template',
    'template': {
        'name': TEMPLATE_NAME,
        'language': {
            'code': 'en'
        },
        'components': [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Debug User"},
                    {"type": "text", "text": "Sick Leave: Feeling unwell (Debug)"}
                ]
            }
        ]
    }
}

print(f"--- WhatsApp Debug Tool ---")
print(f"Target: {recipient}")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print(f"--- Sending... ---")

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
    
    if response.status_code == 200:
        print("SUCCESS: The Meta API accepted the request.")
    else:
        print("FAILED: Check the error message above.")
except Exception as e:
    print(f"ERROR: {e}")
