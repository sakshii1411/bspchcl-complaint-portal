from app import app
from extensions import mail
from flask_mail import Message

with app.app_context():
    try:
        to_email = input("Enter recipient email: ").strip()
        msg = Message(
            subject="BSPHCL Portal Test Email",
            recipients=[to_email],
            body="This is a test email from the BSPHCL Consumer Complaint Portal."
        )
        mail.send(msg)
        print("Test email sent successfully.")
    except Exception as e:
        print("Mail sending failed:")
        print(e)
