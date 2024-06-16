import os
from logger import get_logger
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

logger = get_logger(os.path.basename(__file__))

SCOPES = [os.getenv('SCOPES')]


def main():
    creds = None
    if os.path.exists('token.json'):
        logger.debug("Token file already exists")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        logger.debug("Token file is incorrect or corrupted. Trying to refresh")
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            logger.debug("Creating token file")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    build('sheets', 'v4', credentials=creds)
    logger.debug("Connection to Google Sheets was successful")


if __name__ == '__main__':
    main()

