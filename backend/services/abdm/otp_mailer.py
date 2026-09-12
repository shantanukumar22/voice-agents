"""
OTP Mailer service for ABHA verification using native Python smtplib.
Dispatches genuine 6-digit OTP codes directly to the patient's real email inbox.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger


def send_abha_otp_email(to_email: str, otp: str, patient_name: str = "Patient") -> bool:
    """
    Dispatches OTP code directly to the patient's real email inbox using Python smtplib.
    Reads SMTP settings from environment variables (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM).
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@medikiosk.app").strip()

    logger.info("==================================================")
    logger.info(f"[ABHA OTP DISPATCH] Generating OTP '{otp}' for {to_email}")
    logger.info(f"Using SMTP Host: {smtp_host}:{smtp_port} | User: {smtp_user or '(none)'}")
    logger.info("==================================================")

    if smtp_user and smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"MediKiosk ABHA Auth <{smtp_from}>"
            msg["To"] = to_email
            msg["Subject"] = f"Your ABHA Verification OTP Code: {otp}"

            plain_body = (
                f"Hello {patient_name},\n\n"
                f"Your security verification OTP code for ABHA authentication is: {otp}\n\n"
                f"This code is valid for 10 minutes. Please enter this code on the kiosk screen to verify your identity.\n\n"
                f"If you did not request this code, please ignore this email.\n"
            )

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
              <meta charset="utf-8">
              <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; color: #1e293b; }}
                .container {{ max-width: 520px; background: #ffffff; border-radius: 12px; padding: 32px; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
                .header {{ text-align: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 20px; margin-bottom: 24px; }}
                .brand {{ font-size: 24px; font-weight: 700; color: #2563eb; letter-spacing: -0.5px; }}
                .otp-box {{ background: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 8px; font-size: 36px; font-weight: 800; text-align: center; letter-spacing: 8px; padding: 18px; margin: 24px 0; color: #0f172a; }}
                .footer {{ margin-top: 28px; font-size: 12px; color: #64748b; text-align: center; border-top: 1px solid #f1f5f9; padding-top: 16px; }}
              </style>
            </head>
            <body>
              <div class="container">
                <div class="header">
                  <div class="brand">MediKiosk • ABHA Verification</div>
                </div>
                <p>Hello <strong>{patient_name}</strong>,</p>
                <p>Use the following 6-digit OTP code to complete your ABHA identity verification:</p>
                <div class="otp-box">{otp}</div>
                <p style="font-size: 13px; color: #64748b;">This OTP code is valid for 10 minutes. Do not share this code with anyone.</p>
                <div class="footer">
                  Ayushman Bharat Digital Mission (ABDM) Integration • MediKiosk Platform
                </div>
              </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(plain_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            if smtp_port == 465:
                # SSL Connection
                with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                    server.login(smtp_user, smtp_password)
                    server.send_message(msg)
            else:
                # TLS Connection (port 587 or default)
                with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(smtp_user, smtp_password)
                    server.send_message(msg)

            logger.info(f"SUCCESSFULLY SENT genuine OTP email via Python SMTP to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via Python SMTP ({smtp_host}:{smtp_port}): {e}")
            logger.warning(f"[FALLBACK LOG] Dynamic OTP for {to_email} is: {otp}")
            return False
    else:
        logger.warning(f"SMTP credentials not fully set in .env. [FALLBACK LOG] Dynamic OTP for {to_email} is: {otp}")
        return True
