import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
import requests


load_dotenv()

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USER)

# REQUIRED = [
#     "EMAIL_HOST",
#     "EMAIL_PORT",
#     "EMAIL_USER",
#     "EMAIL_PASSWORD",
#     "EMAIL_FROM",
# ]


MAILJET_API_KEY = os.getenv("MAILJET_API_KEY")
MAILJET_SECRET_KEY = os.getenv("MAILJET_SECRET_KEY")
MAILJET_FROM_EMAIL = os.getenv("MAILJET_FROM_EMAIL")
MAILJET_FROM_NAME = os.getenv("MAILJET_FROM_NAME", "Digital Mixology")

REQUIRED = [
    "MAILJET_API_KEY",
    "MAILJET_SECRET_KEY",
    "MAILJET_FROM_EMAIL",
]

for v in REQUIRED:
    if not os.getenv(v):
        raise RuntimeError(f"Missing env var: {v}")


def send_email_api(to_email: str, body: str):
    html_body = f"""
      <html>
        <body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial, Helvetica, sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td align="center" style="padding:40px 20px;">
                <table width="100%" max-width="600" cellpadding="0" cellspacing="0"
                      style="background-color:#ffffff; border-radius:8px; padding:30px;">
                  
                  <tr>
                    <td style="text-align:center; padding-bottom:20px;">
                      <h2 style="margin:0; color:#072338;">
                        7MA Presentation Generator
                      </h2>
                    </td>
                  </tr>

                  <tr>
                    <td style="color:#333333; font-size:16px; line-height:1.6;">
                      <p style="margin-top:0;">
                        Hello,
                      </p>

                      <p>
                        Your <strong>7MA presentation</strong> has been prepared and is now available to <a href="{body}">view here</a>.
                      </p>

                      

                      <p style="margin-top:30px;">
                        Best regards,<br>
                        Digital Mixology
                      </p>
                    </td>
                  </tr>

                </table>

                <p style="font-size:12px; color:#888888; margin-top:20px;">
                  This is an automated message. Please do not reply.
                </p>
              </td>
            </tr>
          </table>
        </body>
      </html>
      """

    payload = {
        "Messages": [
            {
                "From": {
                    "Email": MAILJET_FROM_EMAIL,
                    "Name": MAILJET_FROM_NAME,
                },
                "To": [
                    {
                        "Email": to_email,
                    }
                ],
                "Subject": "Your 7MA Presentation is Ready",
                "HTMLPart": html_body,
            }
        ]
    }

    response = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(MAILJET_API_KEY, MAILJET_SECRET_KEY),
        json=payload,
        timeout=10,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Mailjet API error {response.status_code}: {response.text}"
        )

    print(f"✅ Mailjet email sent to {to_email}")



def send_email_smtp(to: str, body: str):
    """
    Send an email with the slides URL.
    Raises RuntimeError if email environment variables are not configured.
    """
    # Validate email configuration at runtime (not at import time)
    # This allows the module to be imported even if email is not configured
    missing_vars = [v for v in REQUIRED if not os.getenv(v)]
    if missing_vars:
        raise RuntimeError(
            f"Email configuration missing. Required environment variables not set: {', '.join(missing_vars)}. "
            f"Please configure email settings in your Render environment variables."
        )
    
    # Get fresh values in case they were set after import
    email_host = os.getenv("EMAIL_HOST")
    email_port = int(os.getenv("EMAIL_PORT", 587))
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_PASSWORD")
    email_from = os.getenv("EMAIL_FROM", email_user)
    
    
    msg = MIMEMultipart()
    msg['From'] = email_from
    msg['To'] = to
    msg['Subject'] = "Your 7MA Presentation is Ready"

        # HTML body with hyperlink
    html_body = f"""
    <html>
      <body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial, Helvetica, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td align="center" style="padding:40px 20px;">
              <table width="100%" max-width="600" cellpadding="0" cellspacing="0"
                     style="background-color:#ffffff; border-radius:8px; padding:30px;">
                
                <tr>
                  <td style="text-align:center; padding-bottom:20px;">
                    <h2 style="margin:0; color:#072338;">
                      7MA Presentation Generator
                    </h2>
                  </td>
                </tr>

                <tr>
                  <td style="color:#333333; font-size:16px; line-height:1.6;">
                    <p style="margin-top:0;">
                      Hello,
                    </p>

                    <p>
                      Your <strong>7MA presentation</strong> has been prepared and is now available to <a href="{body}">view here</a>.
                    </p>

                    

                    <p style="margin-top:30px;">
                      Best regards,<br>
                      Digital Mixology
                    </p>
                  </td>
                </tr>

              </table>

              <p style="font-size:12px; color:#888888; margin-top:20px;">
                This is an automated message. Please do not reply.
              </p>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        with smtplib.SMTP(email_host, email_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(email_user, email_password)
            server.send_message(msg)
        print(f"✅ Email sent successfully to {to}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise  # Re-raise so the caller can handle it

if __name__ == "__main__":
    print("Testing email sending...")