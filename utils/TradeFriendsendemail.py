import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import smtplib, ssl
from email.message import EmailMessage

def send_email_with_attachment(sender_email, sender_password, receiver_emails, subject, body, file_path):
    """
    Send email with an attachment.
    Works with Gmail/Outlook/etc. (make sure SMTP settings are correct).
    """

    # Create message container
    msg = MIMEMultipart()
    msg["From"] = sender_email
    if isinstance(receiver_emails, list):
        msg["To"] = ", ".join(receiver_emails)
    else:
        msg["To"] = receiver_emails
    msg["Subject"] = subject

    # Body
    msg.attach(MIMEText(body, "plain"))

    # Attach file
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(file_path)}")
            msg.attach(part)

    # Send email via SMTP server
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)  # Gmail SMTP
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_emails, msg.as_string())
        server.quit()
        print(f"📧 Email sent successfully to {msg['To']}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def send_email_with_attachments(sender_email, sender_password, receiver_emails, subject, body, file_paths):
    msg = EmailMessage()
    msg["From"] = sender_email
    msg["To"] = ", ".join(receiver_emails)
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach multiple files
    for file_path in file_paths:
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
                file_name = file_path.split(os.sep)[-1]
                msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=file_name)
        except Exception as e:
            print(f"⚠️ Failed to attach {file_path}: {e}")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)
