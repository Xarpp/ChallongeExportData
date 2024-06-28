import os

import requests
import json

from logger import get_logger

loggerDis = get_logger(os.path.basename(__file__))


class DiscordSender:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        loggerDis.info("Starting discord sender application")

    def send_message(self, message):
        message['color'] = os.getenv("EMBEDS_COLOR")
        mess = {
            'embeds': [message]
        }
        response = requests.post(self.webhook_url, data=json.dumps(mess), headers={'Content-Type': 'application/json'})
        if response.status_code != 204:
            error_message = f'Request to webhook returned an error {response.status_code},the response is:\n{response.text}'
            raise ValueError(error_message)
