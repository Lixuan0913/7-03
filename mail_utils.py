from flask_mail import Mail , Message
from flask import render_template
import logging
import traceback
from dotenv import load_dotenv
import os
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")

mail=Mail()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

s=URLSafeTimedSerializer(SECRET_KEY)

def init_mail(app):
    """Initialize Flask-Mail with application configuration"""
    # Set email configuration
    app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER")
    app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
    app.config['MAIL_USE_TLS'] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    app.config['MAIL_USE_SSL'] = os.getenv("MAIL_USE_SSL", "False").lower() == "true"
    app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")  
    app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")  
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_DEFAULT_SENDER")
    
    # Initialize mail with app
    mail.init_app(app)
    logging.info("Flask-Mail initialized")

def generate_token(email):
    return s.dumps(email, salt="email-confirm")

def confirm_token(token, expiration=3600):
    try:
        return s.loads(token, salt="email-confirm", max_age=expiration)
    except SignatureExpired:
        logging.warning("Verification token expired.")
        return None
    except BadSignature:
        logging.warning("Inavlid verification token.")
        return None

def send_verification_email(to, verify_url):
    try:
        msg = Message(
            subject="Verify Your Acount",
            recipients=[to],
            html=render_template('verify_email.html', verify_url=verify_url),
            sender=("No-Reply YouMMU Reviews", "lixuanyap4@gmail.com")
        )
        mail.send(msg)
        logging.info(f"Verification email sent to {to} .")
        return True
    except Exception as e:
        logging.error(f"Error send email to {to}: {str(e)}")
        logging.error(traceback.format_exc())

    
def send_reset_email(to,reset_url):
    try:
        msg = Message(
            subject="Reset Password",
            recipients=[to],
            html=render_template('reset_email.html', reset_url=reset_url),
            sender=("No-Reply YouMMU Reviews", "lixuanyap4@gmail.com")
        )
        mail.send(msg)
        logging.info(f"Verification email sent to {to} .")
        return True
    
    except Exception as e:
        logging.error(f"Error sending reset email to {to}: {str(e)}")
        logging.error(traceback.format_exc())
        return False