import os.path

from dotenv import load_dotenv, find_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from logger import get_logger

load_dotenv(find_dotenv(), verbose=True, override=True)

loggerSheet = get_logger(os.path.basename(__file__))


class GoogleSheetsManager:
    SCOPES = [os.getenv('SCOPES')]

    def __init__(self, spreadsheet_id, default_range_name):
        self.spreadsheet_id = spreadsheet_id
        self.default_range_name = default_range_name
        self.sheet = None
        self.service = None

        service_account_files = [os.getenv('SHEET_SERVICE_ACCOUNT_FILE'),
                                 os.getenv('SHEET_SERVICE_ACCOUNT_FILE_RESERVE')]

        for file in service_account_files:
            try:
                loggerSheet.info(f"Attempting connection with {file}")
                creds = Credentials.from_service_account_file(file,
                                                              scopes=self.SCOPES)
                self.service = build('sheets', 'v4', credentials=creds)
                self.sheet = self.service.spreadsheets()
                loggerSheet.info("Connection to Google Sheets was successful")
                break
            except HttpError as error:
                loggerSheet.error(f'An error occurred with {file}: {error}')
                continue

        if self.service is None:
            loggerSheet.critical("Failed to connect to any service account")

    def write_data(self, range_name, values):
        body = {
            'values': [values]
        }
        result = self.sheet.values().update(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()
        loggerSheet.debug(f'Writing data. Range - {range_name}. {result.get("updatedCells")} cells updated')

    def append_to_last_empty_row(self, range_name, values):
        body = {
            'values': values
        }
        self.sheet.values().append(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', insertDataOption='OVERWRITE', body=body).execute()
        loggerSheet.debug("New row has been added to the table")

    def get_users_data(self):
        loggerSheet.debug("Getting user data")
        result = self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=self.default_range_name).execute()
        values = result.get('values', [])
        if not values:
            loggerSheet.debug("No data found")
        else:
            loggerSheet.debug("Data received successfully ")
            return values

    def add_new_user(self, user):
        loggerSheet.debug("Adding a new user")
        self.append_to_last_empty_row(self.default_range_name, [
            [user.username, user.elo, user.calibration, user.matches_played, user.matches_won, user.tournaments_played],
        ])
        loggerSheet.debug("User added successfully")

    def update_user_by_username(self, user):
        loggerSheet.info(f'Updating ELO for {user.username}. New ELO - {user.elo}')
        values = self.get_users_data()
        len = 2
        for row in values:
            if row[0] == user.username:
                break
            len += 1
        self.write_data(f"{os.getenv('SHEET_LIST')}!B{len}:F{len}", [user.elo, user.calibration,
                                                                     user.matches_played, user.matches_won,
                                                                     user.tournaments_played])
        loggerSheet.debug(f'ELO has been successfully changed. Row number - {len}')
