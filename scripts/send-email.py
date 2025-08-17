# using SendGrid's Python Library
# https://github.com/sendgrid/sendgrid-python
import os
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Load environment variables from .env file
load_dotenv()

# Check if API key exists
api_key = os.getenv('SENDGRID_API_KEY')
if not api_key:
    print("Error: SENDGRID_API_KEY environment variable is not set")
    exit(1)

print(f"Using API key: {api_key[:10]}..." if len(api_key) > 10 else "API key found")

message = Mail(
    from_email='contact@digi-permit.org',
    to_emails='to@example.com',
    subject='Sending with Twilio SendGrid is Fun',
    html_content='<strong>and easy to do anywhere, even with Python</strong>')

try:
    sg = SendGridAPIClient(api_key)
    # sg.set_sendgrid_data_residency("eu")
    # uncomment the above line if you are sending mail using a regional EU subuser
    response = sg.send(message)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.body}")
    print(f"Response Headers: {response.headers}")
except Exception as e:
    print(f"Error occurred: {e}")
    print(f"Error type: {type(e).__name__}")
    
    # Handle specific SendGrid errors
    if hasattr(e, 'status_code'):
        print(f"HTTP Status Code: {e.status_code}")
    if hasattr(e, 'body'):
        print(f"Error Body: {e.body}")