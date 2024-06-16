import os

import requests
import json

from dotenv import load_dotenv

from logger import get_logger

load_dotenv()

logger = get_logger(os.path.basename(__file__))

webhook_url = (os.getenv("DISCORD_WEBHOOK_URL"))
logger.debug("Starting discord sender application")


def send_message(message):
    payload = {
        'content': message
    }
    response = requests.post(webhook_url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
    if response.status_code != 204:
        error_message = f'Request to webhook returned an error {response.status_code}, the response is:\n{response.text}'
        raise ValueError(error_message)
