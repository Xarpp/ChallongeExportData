import random
import traceback
from time import sleep

from requests import HTTPError

from discord_bot import *
import challonge
from google_sheets_manager import *
from match import Match
from users import *
from team import *
import os
from dotenv import load_dotenv, find_dotenv

loggerTour = get_logger(os.path.basename(__file__))


def get_value_or_env(value, env_var_name):
    if value is None:
        try:
            value = os.getenv(env_var_name)
        except AttributeError:
            loggerTour.error(f"It failed to retrieve the value for {env_var_name} from the environment.")
    return value


def get_obj_by_id(obj_id, mass):
    for obj in mass:
        if obj.id == obj_id:
            return obj
    return None


def sort_key(element):
    state_priorities = {'pending': 0, 'complete': 1, 'open': 2}
    return state_priorities[element['state']]

class Tournament:
    def __init__(self, tournament_url=None, sheet_list=None, webhook_url=None, tournament_format=1):
        load_dotenv(find_dotenv(), verbose=True, override=True)
        self.participants_list = []
        self.team_list = []
        self.matches_list = []
        self.tournamentID = 0
        self.tournament_format = tournament_format

        self.tournament_url = get_value_or_env(tournament_url, 'TOURNAMENT_URL')
        self.sheet_list = get_value_or_env(sheet_list, 'SHEET_LIST')
        self.webhook_url = get_value_or_env(webhook_url, 'DISCORD_WEBHOOK_URL')

        self.googleSheetsManager = GoogleSheetsManager(os.getenv("SHEET_ID"), self.sheet_list + "!" +
                                                       os.getenv("SHEET_RANGE"))

        self.discordSender = DiscordSender(self.webhook_url)

    def initialize_match(self, teams=None):
        loggerTour.debug(self.tournament_url)
        loggerTour.info("Start application")
        challonge.set_credentials(os.getenv('CHALLONGE_LOGIN'), os.getenv('CHALLONGE_API_KEY'))

        tournament_info = challonge.tournaments.show(self.tournament_url)
        self.tournamentID = tournament_info["id"]

        participants = challonge.participants.index(self.tournamentID)

        if not teams:
            self.parse_users_from_sheets(participants)
            self.start_polling_solo()

        else:
            self.parse_teams_from_sheets(participants, teams)
            self.start_polling_team()

    def set_elo_changes(self, player1, player2):
        K1 = K2 = 50

        if player1.calibration > 0:
            K1 = 200

        if player2.calibration > 0:
            K2 = 200

        EA1 = 1 / (1 + pow(10, (player2.elo - player1.elo) / 400))
        EA2 = 1 / (1 + pow(10, (player1.elo - player2.elo) / 400))

        player1.r_win = int(K1 * (1 - EA1))
        player1.r_lose = int(K1 * (0 - EA1))

        player2.r_win = int(K2 * (1 - EA2))
        player2.r_lose = int(K2 * (0 - EA2))

        if self.tournament_format == 2:
            player1.set_avg_elo()
            player2.set_avg_elo()

    def parse_users_from_sheets(self, participants):
        loggerTour.debug("Parsing user's from sheets")
        users_sheets = self.googleSheetsManager.get_users_data()

        for participant in participants:
            user_name = participant['name']
            user_id = participant['id']

            if users_sheets is None:
                existing_user = None
            else:
                filtered_sheets = [sheet for sheet in users_sheets if sheet]
                existing_user = next((sheet for sheet in filtered_sheets if sheet[0] == user_name), None)

            if not existing_user:
                user_obj = User(username=user_name, elo=1000, calibration=10, id=user_id)
                self.googleSheetsManager.add_new_user(user_obj)
                loggerTour.debug(f'Created new user. Username - {user_obj.username}. ELO - {user_obj.elo}. '
                                 f'Calibration - {user_obj.calibration}')
            else:
                user_obj = User(username=existing_user[0], elo=int(existing_user[1]), calibration=int(existing_user[2]),
                                matches_played=int(existing_user[3]), matches_won=int(existing_user[4]),
                                tournaments_played=int(existing_user[5]) + 1, id=user_id)
                loggerTour.debug(f'User {user_obj.username} already exists.')

            self.participants_list.append(user_obj)

    def parse_teams_from_sheets(self, participants, teams):
        loggerTour.debug("Parsing team's from sheets")
        users_sheets = self.googleSheetsManager.get_users_data()
        for team_name, players in teams.items():
            for participant in participants:
                if team_name == participant["name"]:
                    team = Team(participant["id"], team_name)
                    for player in players:
                        if users_sheets is None:
                            existing_user = None
                        else:
                            filtered_sheets = [sheet for sheet in users_sheets if sheet]
                            existing_user = next((sheet for sheet in filtered_sheets if sheet[0] == player), None)

                        if not existing_user:
                            user_obj = User(username=player, elo=1000, calibration=10,
                                            id=random.randint(10_000_000, 99_999_999))
                            self.googleSheetsManager.add_new_user(user_obj)
                            loggerTour.debug(f'Created new user. Username - {user_obj.username}. ELO - {user_obj.elo}. '
                                             f'Calibration - {user_obj.calibration}')
                        else:
                            user_obj = User(username=existing_user[0], elo=int(existing_user[1]),
                                            calibration=int(existing_user[2]),
                                            matches_played=int(existing_user[3]), matches_won=int(existing_user[4]),
                                            tournaments_played=int(existing_user[5]) + 1,
                                            id=random.randint(10_000_000, 99_999_999))
                            loggerTour.debug(f'User {user_obj.username} already exists.')
                        team.teammates.append(user_obj)

                    self.team_list.append(team)

    def waiting_match_start(self, state):
        while state == "pending":
            loggerTour.debug("Waiting for the start of the tournament...")
            state = challonge.tournaments.show(self.tournamentID)['state']
            sleep(2)

    def create_matches(self, matches):
        for match in matches:
            exiting_match = get_obj_by_id(match["id"], self.matches_list)
            if not exiting_match:
                player1 = player2 = None
                if self.tournament_format == 1:
                    player1 = get_obj_by_id(match["player1_id"], self.participants_list)
                    player2 = get_obj_by_id(match["player2_id"], self.participants_list)
                elif self.tournament_format == 2:
                    player1 = get_obj_by_id(match["player1_id"], self.team_list)
                    player2 = get_obj_by_id(match["player2_id"], self.team_list)

                new_match = Match(id=match["id"], player1=player1, player2=player2, state=match['state'],
                                  winner_id=match["winner_id"])

                if new_match.player1 is not None and new_match.player2 is not None:
                    self.set_elo_changes(new_match.player1, new_match.player2)
                    if new_match.player1.id == new_match.winner_id:
                        new_match.player1_r_change = player1.r_win
                        new_match.player2_r_change = player2.r_lose
                    else:
                        new_match.player1_r_change = player1.r_lose
                        new_match.player2_r_change = player2.r_win

                self.matches_list.append(new_match)
                loggerTour.debug(f"New match was created. id={new_match.id}")
            else:
                loggerTour.debug(f"Match with id={exiting_match.id} already exists")

    def send_user_list(self, title):
        users_mess_list = ""
        for user in self.participants_list:
            users_mess_list += f"{user.username} ({user.elo} TRP)\n"
        message = {
            "title": title,
            "description": users_mess_list,
        }
        self.discordSender.send_message(message)

    def send_teams_list(self, title):
        message = None
        users_mess_list = ""
        for team in self.team_list:
            users_mess_list += f"Team {team.username}\n"
            for teammate in team.teammates:
                users_mess_list += f"{teammate.username} ({teammate.elo} TRP)\n"
            users_mess_list += "\n"
            message = {
                "title": title,
                "description": users_mess_list,
            }
        self.discordSender.send_message(message)

    def send_upcoming_match(self, player1, player2):
        loggerTour.info(f"New match has started. Player1: {player1.username}. "
                        f"Player2: {player2.username}")
        message = {
            "title": "🏆 New Match Upcoming",
            "description": f"{player1.username} ({player1.elo} TRP) vs {player2.username} ({player2.elo} TRP)",
        }

        if self.tournament_format == 1:
            message['footer'] = {
                "text": "📈 ELO Predictions\n"
                        f"- {player1.username}: +{player1.r_win} (W) / {player1.r_lose} (L)\n"
                        f"- {player2.username}: +{player2.r_win} (W) / {player2.r_lose} (L)",
            }

        self.discordSender.send_message(message)

    def send_finished_match(self, player1, player2):
        loggerTour.info(f"Match is over. Player1: {player1.username}. "
                        f"Player2: {player2.username}")

        if player1.winner:
            description = f"(W) {player1.username} ({player1.elo} TRP)  vs {player2.username} ({player2.elo} TRP)"
        else:
            description = f"{player1.username} ({player1.elo} TRP)  vs (W) {player2.username} ({player2.elo} TRP)"
        message = {
            "title": "🏁 Finished match",
            "description": description,
        }

        self.discordSender.send_message(message)

    def start_polling_solo(self):
        try:
            loggerTour.info("Processing of the tournament has start")
            tournament_info = challonge.tournaments.show(self.tournament_url)
            state = tournament_info["state"]

            if state != "complete":
                self.waiting_match_start(state)

                loggerTour.info(f"Tournament has start. ID: {self.tournamentID}")
                self.send_user_list("📋 Tournament lineup: ")

                self.create_matches(challonge.matches.index(self.tournamentID))

                while state != 'complete':
                    try:
                        sorted_elements = sorted(challonge.matches.index(self.tournamentID), key=sort_key)
                        self.processing_matches(sorted_elements)
                        sleep(2)
                        state = challonge.tournaments.show(self.tournamentID)['state']
                    except HTTPError as e:
                        print("Произошла ошибка HTTP:", e)
                        sleep(5)
                    except Exception as e:
                        print("Произошла другая ошибка:", e)
                        sleep(5)

                loggerTour.info(f"The tournament is over. ID: {self.tournamentID}")

                self.send_user_list("📋 Tournament is over! Updated rating:")

        except ValueError as ex:
            loggerTour.error(ex.args[0])
        except Exception as ex:
            error_message = f"Tournament with URL: {self.tournament_url} has ERROR: {str(ex)}"
            stack_trace = traceback.format_exc()
            full_error_message = f"{error_message}\n{stack_trace}"

            loggerTour.error(full_error_message)

    def start_polling_team(self):
        loggerTour.info("Processing of the tournament has start")
        tournament_info = challonge.tournaments.show(self.tournament_url)
        state = tournament_info["state"]

        if state != "complete":
            self.waiting_match_start(state)

            loggerTour.info(f"Tournament has start. ID: {self.tournamentID}")
            self.send_teams_list("📋 Tournament lineup: ")

            for team in self.team_list:
                team.set_avg_elo()

            self.create_matches(challonge.matches.index(self.tournamentID))

            while state != 'complete':
                try:
                    sorted_elements = sorted(challonge.matches.index(self.tournamentID), key=sort_key)
                    self.processing_matches(sorted_elements)
                    sleep(2)
                    state = challonge.tournaments.show(self.tournamentID)['state']
                except HTTPError as e:
                    print("Произошла ошибка HTTP:", e)
                    sleep(5)
                except Exception as e:
                    print("Произошла другая ошибка:", e)
                    sleep(5)

            loggerTour.info(f"The tournament is over. ID: {self.tournamentID}")

            self.send_teams_list("📋 Tournament is over! Updated rating:")

    def refund_elo_in_sheets(self, players):
        loggerTour.debug("Refund ELO for players")
        for player in players:
            player.calibration += 1 if player.calibration > 0 else 0
            player.matches_played -= 1
            player.matches_won -= 1 if player.winner else 0
            self.googleSheetsManager.update_user_by_username(player)

    def change_elo_in_sheets(self, players):
        loggerTour.debug("Updating ELO for players")
        for player in players:
            player.calibration -= 1 if player.calibration > 0 else 0
            player.matches_played += 1
            player.matches_won += 1 if player.winner else 0
            player.elo += player.r_win if player.winner else player.r_lose
            self.googleSheetsManager.update_user_by_username(player)

    def refund_elo(self, match_obj):
        match_obj.player1.elo -= match_obj.player1_r_change
        match_obj.player2.elo -= match_obj.player2_r_change

        match_obj.player1.r_change = match_obj.player1_r_change
        match_obj.player2.r_change = match_obj.player2_r_change

        if match_obj.winner_id == match_obj.player1.id:
            match_obj.player1.winner = True
            match_obj.player2.winner = False
        else:
            match_obj.player1.winner = False
            match_obj.player2.winner = True

        if self.tournament_format == 1:
            self.refund_elo_in_sheets([match_obj.player1, match_obj.player2])

        elif self.tournament_format == 2:
            for team in [match_obj.player1, match_obj.player2]:
                for player in team.teammates:
                    player.winner = team.winner
                    if player.calibration > 0:
                        player.elo -= team.r_change * 4
                    else:
                        player.elo -= team.r_change
                    self.refund_elo_in_sheets([player])
                team.set_avg_elo()

    def set_new_elo(self, player1, player2, winner_id, match_obj):
        self.set_elo_changes(player1, player2)
        if player1.id == winner_id:
            match_obj.player1_r_change = player1.r_win
            match_obj.player2_r_change = player2.r_lose
            player1.winner = True
            player2.winner = False
        else:
            match_obj.player1_r_change = player1.r_lose
            match_obj.player2_r_change = player2.r_win
            player2.winner = True
            player1.winner = False
        if self.tournament_format == 1:
            self.change_elo_in_sheets([player1, player2])
        elif self.tournament_format == 2:
            for team in [player1, player2]:
                for player in team.teammates:
                    player.winner = team.winner
                    r_win = team.r_win * 4 if player.calibration > 0 else team.r_win
                    r_lose = team.r_lose * 4 if player.calibration > 0 else team.r_lose
                    player.r_win = r_win
                    player.r_lose = r_lose
                    self.change_elo_in_sheets([player])
                team.set_avg_elo()

    def start_process(self, match, exiting_match, player1, player2):
        if match['state'] == "pending":
            if exiting_match.state == "complete":
                self.refund_elo(exiting_match)

        elif match['state'] == "open":
            if exiting_match.state == "open" and exiting_match.sent:
                return
            if exiting_match.state == "complete":
                self.refund_elo(exiting_match)
            exiting_match.sent = True

            self.set_elo_changes(player1, player2)
            self.send_upcoming_match(player1, player2)

        elif match['state'] == "complete":
            if exiting_match.state == "complete":
                if exiting_match.winner_id != match['winner_id']:
                    self.refund_elo(exiting_match)
                    self.set_new_elo(player1, player2, match['winner_id'], exiting_match)
            if exiting_match.state == "open":
                self.set_new_elo(player1, player2, match['winner_id'], exiting_match)

            exiting_match.winner_id = match['winner_id']
            self.send_finished_match(player1, player2)

        sleep(1)

    def processing_matches(self, current_matches):
        for match in current_matches:
            exiting_match = get_obj_by_id(match['id'], self.matches_list)

            if not exiting_match:
                self.create_matches(current_matches)
                continue

            if exiting_match.updated == match['updated_at']:
                continue

            player1 = player2 = None

            if self.tournament_format == 1:
                player1 = get_obj_by_id(match['player1_id'], self.participants_list)
                player2 = get_obj_by_id(match['player2_id'], self.participants_list)
                self.start_process(match, exiting_match, player1, player2)
            elif self.tournament_format == 2:
                player1 = get_obj_by_id(match['player1_id'], self.team_list)
                player2 = get_obj_by_id(match['player2_id'], self.team_list)
                self.start_process(match, exiting_match, player1, player2)

            exiting_match.player1 = player1
            exiting_match.player2 = player2
            exiting_match.state = match['state']
            exiting_match.updated = match['updated_at']


if __name__ == "__main__":
    tournament = Tournament('rxl9401c', 'test',
                            'https://discord.com/api/webhooks/1259248833867550790/KuLu9OzNkOaVOTuul56_cjZTVXem77R8TUn9dwNpyxhctHCkFSZl15hYfkBx442bCLrB')
    tournament.initialize_match({'GG': ['1', '2'], 'FG': ['3', '4'], 'GFFG': ['5', '6']})
