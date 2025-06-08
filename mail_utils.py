import os
import logging
import traceback
from threading import Thread
from flask import render_template, current_app
import secrets
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# Load environment variables
load_dotenv()
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Token serializer
s = URLSafeTimedSerializer(SECRET_KEY)

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

# ✅ Background email sending
def send_email_async(app, subject, to, html_content):
    with app.app_context():
        try:
            message = Mail(
                from_email=Email(MAIL_DEFAULT_SENDER, name="No-Reply YouMMU Reviews"),
                to_emails=To(to),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            sg = SendGridAPIClient(api_key=SENDGRID_API_KEY)
            response = sg.send(message)
            logging.info(f"Email sent to {to}. Status code: {response.status_code}")
        except Exception as e:
            logging.error(f"Async error sending email to {to}: {str(e)}")
            logging.error(traceback.format_exc())

# ✅ Kick off thread without blocking
def send_email(subject, to, html_content):
    try:
        app = current_app._get_current_object()  # Safe access to app context
        Thread(target=send_email_async, args=(app, subject, to, html_content)).start()
        return True  # Return immediately
    except Exception as e:
        logging.error(f"Error starting email thread: {str(e)}")
        return False

# Verification email
def send_verification_email(to, verify_url):
    try:
        html = render_template('verify_email.html', verify_url=verify_url)
        return send_email("Verify Your Account", to, html)
    except Exception as e:
        logging.error(f"Error in send_verification_email: {str(e)}")
        logging.error(traceback.format_exc())
        return False

# Reset email
def send_reset_email(to, reset_url):
    try:
        html = render_template('reset_email.html', reset_url=reset_url)
        return send_email("Reset Password", to, html)
    except Exception as e:
        logging.error(f"Error in send_reset_email: {str(e)}")
        logging.error(traceback.format_exc())
        return False
