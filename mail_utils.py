import os
import logging
import traceback
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from flask import render_template
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# Load environment variables
load_dotenv()

# Setup logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load secret key
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")

# Create serializer for token handling
s = URLSafeTimedSerializer(SECRET_KEY)

# Load SendGrid settings
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

def generate_token(email):
    return s.dumps(email, salt="email-confirm")

def confirm_token(token, expiration=3600):
    try:
        return s.loads(token, salt="email-confirm", max_age=expiration)
    except SignatureExpired:
        logging.warning("Verification token expired.")
        return None
    except BadSignature:
        logging.warning("Invalid verification token.")
        return None

def send_email(subject, to, html_content):
    try:
        message = Mail(
            from_email=Email(MAIL_DEFAULT_SENDER, name="No-Reply YouMMU Reviews"),
            to_emails=To(to),
            subject=subject,
            html_content=Content("text/html", html_content)
        )

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        logging.info(f"Email sent to {to}. Status code: {response.status_code}")
        return True
    except Exception as e:
        logging.error(f"Error sending email to {to}: {str(e)}")
        logging.error(traceback.format_exc())
        return False

def send_verification_email(to, verify_url):
    try:
        html = render_template('verify_email.html', verify_url=verify_url)
        return send_email("Verify Your Account", to, html)
    except Exception as e:
        logging.error(f"Error in send_verification_email: {str(e)}")
        logging.error(traceback.format_exc())
        return False

def send_reset_email(to, reset_url):
    try:
        html = render_template('reset_email.html', reset_url=reset_url)
        return send_email("Reset Password", to, html)
    except Exception as e:
        logging.error(f"Error in send_reset_email: {str(e)}")
        logging.error(traceback.format_exc())
        return False
