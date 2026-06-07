
import os
 
CONFIG = {
    "GROQ_API_KEY":        os.environ.get("GROQ_API_KEY", ""),
    "SENDER_EMAIL":        os.environ.get("SENDER_EMAIL", ""),
    "GMAIL_APP_PASSWORD":  os.environ.get("GMAIL_APP_PASSWORD", ""),
    "RECIPIENT_EMAIL":     os.environ.get("RECIPIENT_EMAIL", ""),
}
 