"""
Centralized hardcoded configuration for Mock ABHA verification and patient profile.
You can edit the values in this file to customize your test patient data.
"""

# Default hardcoded ABHA ID (with and without dashes)
HARDCODED_ABHA_ID = "91-1234-5678-9012"
HARDCODED_ABHA_NUMBER = "91123456789012"

# Associated contact info (Real test email inbox for Python SMTP delivery)
HARDCODED_EMAIL = "arpitbedai@gmail.com"
HARDCODED_PHONE = "+919876543210"

# Patient demographic details stored into Supabase upon OTP verification
HARDCODED_PATIENT_NAME = "Rahul Sharma"
HARDCODED_GENDER = "Male"
HARDCODED_DOB = "1995-08-20"
HARDCODED_ADDRESS = "Flat 402, Green Acres, New Delhi"
HARDCODED_ABHA_ADDRESS = "rahul.sharma@abdm"

def get_masked_email(email: str = HARDCODED_EMAIL) -> str:
    """Helper to return a masked version of the email (e.g., ar***@gmail.com)."""
    if not email or "@" not in email:
        return "ar***@gmail.com"
    parts = email.split("@")
    name = parts[0]
    domain = parts[1]
    masked_name = name[:2] + "***" if len(name) > 2 else name[0] + "***"
    return f"{masked_name}@{domain}"
