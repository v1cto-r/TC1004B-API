from twilio.rest import Client
from .settings import settings

client = Client(settings.TWILIO_SID, settings.TWILIO_KEY)

def message(body: str):
    """
    Wrapper function to send a WhatsApp message to the configured number.
    """
    return client.messages.create(
        from_=settings.TWILIO_FROM,
        body=body,
        to=settings.TWILIO_TO
    )