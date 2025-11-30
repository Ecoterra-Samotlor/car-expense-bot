import os
import subprocess
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from config import MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, ADMIN_EMAIL, SMTP_USER, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT

def create_backup():
    filename = f"backup_car_expenses_{datetime.now().strftime('%Y%m%d')}.sql"
    cmd = [
        "mysqldump",
        "-u", MYSQL_USER,
        f"--password={MYSQL_PASSWORD}",
        MYSQL_DATABASE
    ]
    with open(filename, "w") as f:
        subprocess.run(cmd, stdout=f, check=True)
    return filename

def send_email_with_attachment(filename: str):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = ADMIN_EMAIL
    msg["Subject"] = f"MySQL Backup: {filename}"

    with open(filename, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, ADMIN_EMAIL, msg.as_string())

    os.remove(filename)

if __name__ == "__main__":
    f = create_backup()
    send_email_with_attachment(f)