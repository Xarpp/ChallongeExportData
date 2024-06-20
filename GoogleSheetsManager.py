import os.path

from dotenv import load_dotenv, find_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from logger import get_logger


logger = get_logger(os.path.basename(__file__))


class GoogleSheetsManager:
    SCOPES = [os.getenv('SCOPES')]

    def __init__(self, spreadsheet_id, default_range_name):
        logger.debug("Initialization GoogleSheetsManager")
        if os.path.exists('token.json'):
            logger.debug("Token file already exists")
            self.creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
        if not self.creds or not self.creds.valid:
            logger.debug("Token file is incorrect or corrupted. Trying to refresh")
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                logger.debug("Creating token file")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(self.creds.to_json())
        self.service = build('sheets', 'v4', credentials=self.creds)
        self.spreadsheet_id = spreadsheet_id
        self.sheet = self.service.spreadsheets()
        self.default_range_name = default_range_name

        logger.debug("Connection to Google Sheets was successful")

    def write_data(self, range_name, values):
        body = {
            'values': [values]
        }
        result = self.sheet.values().update(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()
        logger.debug(f'Writing data. Range - {range_name}. {result.get("updatedCells")} cells updated')

    def append_to_last_empty_row(self, range_name, values):
        body = {
            'values': values
        }
        self.sheet.values().append(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', insertDataOption='OVERWRITE', body=body).execute()
        logger.debug("New row has been added to the table")

    def get_users_data(self):
        logger.debug("Getting user data")
        result = self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=self.default_range_name).execute()
        values = result.get('values', [])
        if not values:
            logger.debug("No data found")
        else:
            logger.debug("Data received successfully ")
            return values

    def add_new_user(self, user):
        logger.debug("Adding a new user")
        self.append_to_last_empty_row(self.default_range_name, [
            [user.username, user.elo, user.calibration, user.matches_played, user.matches_won, user.tournaments_played],
        ])
        logger.debug("User added successfully")

    def update_user_by_username(self, user):
        logger.debug(f'Updating ELO for {user.username}. New ELO - {user.elo}')
        values = self.get_users_data()
        len = 2
        for row in values:
            if row[0] == user.username:
                break
            len += 1
        self.write_data(f"{os.getenv('SHEET_LIST')}!B{len}:F{len}", [user.elo, user.calibration,
                                                                     user.matches_played, user.matches_won,
                                                                     user.tournaments_played])
        logger.debug(f'ELO has been successfully changed. Row number - {len}')
