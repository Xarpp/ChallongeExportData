import random
from time import sleep
from discord_bot import *
import challonge
from google_sheets_manager import *
from users import *
from team import *
import os
from dotenv import load_dotenv, find_dotenv

loggerTour = get_logger(os.path.basename(__file__))


def get_user_by_id(id, users_list):
    loggerTour.debug("Getting user by id")
    for item in users_list:
        if item.id == id:
            loggerTour.debug("User was successfully found")
            return item
    loggerTour.error(f'User with id - {id} was not found')
    return None


class Tournament:
    def __init__(self, tournament_url=None, sheet_list=None, webhook_url=None):
        load_dotenv(find_dotenv(), verbose=True, override=True)
        self.users_list = []
        self.team_list = []
        self.all_users_from_sheets = []
        self.sent_messages = {}

        self.tournament_url = self.get_value_or_env(tournament_url, 'TOURNAMENT_URL')
        self.sheet_list = self.get_value_or_env(sheet_list, 'SHEET_LIST')
        self.webhook_url = self.get_value_or_env(webhook_url, 'DISCORD_WEBHOOK_URL')

        self.googleSheetsManager = GoogleSheetsManager(os.getenv("SHEET_ID"), self.sheet_list + "!" +
                                                       os.getenv("SHEET_RANGE"))

        self.discordSender = DiscordSender(self.webhook_url)

    def discord_sender(self, message):
        loggerTour.debug("Sending message to Discord Channel")
        self.discordSender.send_message(message)
        loggerTour.debug("Message sent successfully")

    def parse_users_from_sheets(self):
        loggerTour.debug("Parsing user's from sheets")
        users_sheets = self.googleSheetsManager.get_users_data()
        if not users_sheets:
            return
        for user_item in users_sheets:
            if not user_item:
                continue
            self.all_users_from_sheets.append(
                User(username=user_item[0], elo=int(user_item[1]), calibration=int(user_item[2]),
                     matches_played=int(user_item[3]), matches_won=int(user_item[4]),
                     tournaments_played=int(user_item[5])))
            loggerTour.debug(
                f'New User object has been created. Username - {user_item[0]}. ELO - {user_item[1]}. '
                f'Calibration - {user_item[2]}')

    def check_users_in_sheet(self, participants):
        for participant in participants:
            existing_user = next((user for user in self.all_users_from_sheets if user.username == participant['name']),
                                 None)

            if not existing_user:
                new_user = User(username=participant['name'], elo=1000, calibration=10, id=participant['id'])
                self.googleSheetsManager.add_new_user(new_user)
                self.users_list.append(new_user)
                loggerTour.debug(f'Created new user. Username - {new_user.username}. ELO - {new_user.elo}. '
                                  f'Calibration - {new_user.calibration}')
            else:
                existing_user.id = participant['id']
                existing_user.tournaments_played += 1
                self.users_list.append(existing_user)
                loggerTour.debug(f'User {existing_user.username} already exists.')

    def check_teams_in_sheet(self, teams, participants):
        for team_name, players in teams.items():
            for participant in participants:
                if team_name == participant["name"]:
                    team = Team(participant["id"], team_name)
                    for player in players:
                        existing_user = next(
                            (user for user in self.all_users_from_sheets if user.username == player), None)
                        if not existing_user:
                            new_user = User(username=player, elo=1000, calibration=10,
                                            id=random.randint(10_000_000, 99_999_999))
                            self.googleSheetsManager.add_new_user(new_user)
                            team.teammates.append(new_user)
                            loggerTour.debug(
                                f'Created new user. Username - {new_user.username}. ELO - {new_user.elo}. '
                                f'Calibration - {new_user.calibration}')
                        else:
                            existing_user.id = random.randint(10_000_000, 99_999_999)
                            existing_user.tournaments_played += 1
                            team.teammates.append(existing_user)
                            loggerTour.debug(f'User {existing_user.username} already exists.')
                    self.team_list.append(team)

    # def change_solo_elo_in_sheets(self, players):
    #     loggerTour.debug("Updating ELO for players")
    #     for player in players:
    #         player.calibration -= 1 if player.calibration > 0 else 0
    #         player.matches_played += 1
    #         player.matches_won += 1 if player.winner else 0
    #         player.elo += player.r_win if player.winner else player.r_lose
    #         self.googleSheetsManager.update_user_by_username(player)

    # def change_team_elo_in_sheets(self, teams):
    #     loggerTour.debug("Updating ELO for teams")
    #     for team in teams:
    #         for player in team.teammates:
    #             player.calibration -= 1 if player.calibration > 0 else 0
    #             player.matches_played += 1
    #             player.matches_won += 1 if team.winner else 0
    #             player.elo += team.r_win if team.winner else team.r_lose
    #             self.googleSheetsManager.update_user_by_username(player)

    def change_elo_in_sheets(self, player):
        loggerTour.debug("Updating ELO for players")
        player.calibration -= 1 if player.calibration > 0 else 0
        player.matches_played += 1
        player.matches_won += 1 if player.winner else 0
        player.elo += player.r_win if player.winner else player.r_lose
        self.googleSheetsManager.update_user_by_username(player)

    def calculate_solo_match(self, match):
        loggerTour.debug(f'Calculating ELO for matchID - {match["id"]}')
        player1 = get_user_by_id(match['player1_id'], self.users_list)
        player2 = get_user_by_id(match['player2_id'], self.users_list)

        K1 = K2 = 50

        if player1.calibration > 0:
            K1 = 200

        if player2.calibration > 0:
            K2 = 200

        SA1 = 1 if player1.id == match['winner_id'] else 0
        EA1 = 1 / (1 + pow(10, (player2.elo - player1.elo) / 400))

        SA2 = 1 if player2.id == match['winner_id'] else 0
        EA2 = 1 / (1 + pow(10, (player1.elo - player2.elo) / 400))

        # rating_changes1 = int(K1 * (SA1 - EA1))
        # rating_changes2 = int(K2 * (SA2 - EA2))
        #
        # player1.elo += rating_changes1
        # player2.elo += rating_changes2

        if SA1 > 0:
            player1.winner = True
            player2.winner = False
        else:
            player1.winner = False
            player2.winner = True

        loggerTour.debug(f'Player1: K: {K1}, SA: {SA1}, EA: {EA1}')
        loggerTour.debug(f'Player2: K: {K2}, SA: {SA2}, EA: {EA2}')

        self.change_elo_in_sheets(player1)
        self.change_elo_in_sheets(player2)

        return player1, player2

    def calculate_team_match(self, match):
        loggerTour.debug(f'Calculating ELO for matchID - {match["id"]}')
        team1 = get_user_by_id(match['player1_id'], self.team_list)
        team2 = get_user_by_id(match['player2_id'], self.team_list)

        K1 = K2 = 50

        SA1 = 1 if team1.id == match['winner_id'] else 0
        EA1 = 1 / (1 + pow(10, (team2.elo - team1.elo) / 400))

        SA2 = 1 if team2.id == match['winner_id'] else 0
        EA2 = 1 / (1 + pow(10, (team1.elo - team2.elo) / 400))

        # rating_changes1 = int(K1 * (SA1 - EA1))
        # rating_changes2 = int(K2 * (SA2 - EA2))
        #
        # team1.elo += rating_changes1
        # team2.elo += rating_changes2

        if SA1 > 0:
            team1.winner = True
            team2.winner = False
        else:
            team1.winner = False
            team2.winner = True

        loggerTour.debug(f'Player1: K: {K1}, SA: {SA1}, EA: {EA1}')
        loggerTour.debug(f'Player2: K: {K2}, SA: {SA2}, EA: {EA2}')

        for team in [team1, team2]:
            for player in team.teammates:
                player.winner = team.winner
                player.r_win = team.r_win
                player.r_lose = team.r_lose
                self.change_elo_in_sheets(player)

        return team1, team2

    def set_solo_elo_changes(self, match):

        player1 = get_user_by_id(match['player1_id'], self.users_list)
        player2 = get_user_by_id(match['player2_id'], self.users_list)

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

        loggerTour.debug(f"player1.r_win = {player1.r_win}")
        loggerTour.debug(f"player1.r_lose = {player1.r_lose}")

        loggerTour.debug(f"player2.r_win = {player2.r_win}")
        loggerTour.debug(f"player2.r_lose = {player2.r_lose}")

        return player1, player2

    def set_team_elo_changes(self, match):

        team1 = get_user_by_id(match['player1_id'], self.team_list)
        team2 = get_user_by_id(match['player2_id'], self.team_list)

        K1 = K2 = 50

        EA1 = 1 / (1 + pow(10, (team2.elo - team1.elo) / 400))
        EA2 = 1 / (1 + pow(10, (team1.elo - team2.elo) / 400))

        team1.r_win = int(K1 * (1 - EA1))
        team1.r_lose = int(K1 * (0 - EA1))

        team2.r_win = int(K2 * (1 - EA2))
        team2.r_lose = int(K2 * (0 - EA2))

        loggerTour.debug(f"team1.r_win = {team1.r_win}")
        loggerTour.debug(f"team1.r_lose = {team1.r_lose}")

        loggerTour.debug(f"team2.r_win = {team2.r_win}")
        loggerTour.debug(f"team2.r_lose = {team2.r_lose}")

        return team1, team2

    def process_matches_solo(self, current_matches):
        loggerTour.debug("Checking new matches")
        for match in current_matches:
            if match['id'] not in self.sent_messages:
                if match['state'] == 'open':
                    players = self.set_solo_elo_changes(match)

                    player1 = players[0]
                    player2 = players[1]

                    loggerTour.info(f"New match has started. ID: {match['id']}. Player1: {player1.username}. "
                                 f"Player2: {player2.username}")
                    message = {
                        "title": "🏆 New Match Upcoming",
                        "description": f"{player1.username} ({player1.elo} TRP) vs {player2.username} ({player2.elo} TRP)",
                        "footer": {
                            "text": "📈 ELO Predictions\n"
                                    f"- {player1.username}: +{player1.r_win} (W) / {player1.r_lose} (L)\n"
                                    f"- {player2.username}: +{player2.r_win} (W) / {player2.r_lose} (L)",
                        }
                    }

                    self.discord_sender(message)

                    self.sent_messages[match['id']] = 'open'
            elif match['state'] == 'complete':
                if self.sent_messages.get(match['id']) == 'open':
                    players = self.calculate_solo_match(match)

                    loggerTour.info(f"Match is over. ID: {match['id']}. Player1: {players[0].username}. "
                                      f"Player2: {players[1].username}")

                    if players[0].winner:
                        description = f"(W) {players[0].username} ({players[0].elo} TRP)  vs {players[1].username} ({players[1].elo} TRP)"
                    else:
                        description = f"{players[0].username} ({players[0].elo} TRP)  vs (W) {players[1].username} ({players[1].elo} TRP)"
                    message = {
                        "title": "🏁 Finished match",
                        "description": description,
                    }

                    self.discord_sender(message)
                    self.sent_messages[match['id']] = 'complete'

    def process_matches_team(self, current_matches):
        loggerTour.debug("Checking new matches")
        for match in current_matches:
            if match['id'] not in self.sent_messages:
                if match['state'] == 'open':
                    players = self.set_team_elo_changes(match)

                    player1 = players[0]
                    player2 = players[1]

                    loggerTour.info(f"New match has started. ID: {match['id']}. Player1: {player1.username}. "
                                 f"Player2: {player2.username}")
                    message = {
                        "title": "🏆 New Match Upcoming",
                        "description": f"{player1.username} ({player1.elo} TRP) vs {player2.username} ({player2.elo} TRP)",
                        "footer": {
                            "text": "📈 ELO Predictions\n"
                                    f"- {player1.username}: +{player1.r_win} (W) / {player1.r_lose} (L)\n"
                                    f"- {player2.username}: +{player2.r_win} (W) / {player2.r_lose} (L)",
                        }
                    }

                    self.discord_sender(message)

                    self.sent_messages[match['id']] = 'open'
            elif match['state'] == 'complete':
                if self.sent_messages.get(match['id']) == 'open':
                    players = self.calculate_team_match(match)

                    loggerTour.info(f"Match is over. ID: {match['id']}. Player1: {players[0].username}. "
                                      f"Player2: {players[1].username}")

                    if players[0].winner:
                        description = f"(W) {players[0].username} ({players[0].elo} TRP)  vs {players[1].username} ({players[1].elo} TRP)"
                    else:
                        description = f"{players[0].username} ({players[0].elo} TRP)  vs (W) {players[1].username} ({players[1].elo} TRP)"
                    message = {
                        "title": "🏁 Finished match",
                        "description": description,
                    }

                    self.discord_sender(message)
                    self.sent_messages[match['id']] = 'complete'

    def start_polling(self, tournament_url, teams):
        try:
            loggerTour.info("Processing of the tournament has start")
            tournament = challonge.tournaments.show(tournament_url)
            tournamentID = tournament["id"]
            state = tournament["state"]
            loggerTour.debug(state)

            if state != "complete":
                while state == "pending":
                    loggerTour.debug("Waiting for the start of the tournament...")
                    state = challonge.tournaments.show(tournamentID)['state']
                    sleep(2)

                loggerTour.info(f"Tournament has start. ID: {tournamentID}")
                self.parse_users_from_sheets()

                if teams is None:
                    self.check_users_in_sheet(challonge.participants.index(tournamentID))

                    users_mess_list = ""

                    for user in self.users_list:
                        users_mess_list += f"{user.username} ({user.elo} TRP)\n"

                    message = {
                        "title": "📋 Tournament lineup: ",
                        "description": users_mess_list,
                    }

                    self.discord_sender(message)

                    while state != 'complete':
                        matches = challonge.matches.index(tournamentID)
                        self.process_matches_solo(matches)
                        state = challonge.tournaments.show(tournamentID)['state']
                        sleep(2)

                    loggerTour.info(f"The tournament is over. ID: {tournamentID}")
                    users_mess_list = ""
                    for user in self.users_list:
                        users_mess_list += f"{user.username} ({user.elo} TRP)\n"

                    message = {
                        "title": "📋 Tournament is over! Updated rating:",
                        "description": users_mess_list,
                    }

                    self.discord_sender(message)

                elif teams is not None:
                    self.check_teams_in_sheet(teams, challonge.participants.index(tournamentID))

                    users_mess_list = ""

                    for team in self.team_list:
                        users_mess_list += f"Team {team.username}\n"
                        for teammate in team.teammates:
                            users_mess_list += f"{teammate.username} ({teammate.elo} TRP)\n"
                        users_mess_list += "\n"

                    message = {
                        "title": "📋 Tournament lineup: ",
                        "description": users_mess_list,
                    }

                    self.discord_sender(message)
                    for team in self.team_list:
                        team.set_avg_elo()

                    while state != 'complete':
                        matches = challonge.matches.index(tournamentID)
                        self.process_matches_team(matches)
                        state = challonge.tournaments.show(tournamentID)['state']
                        sleep(2)

                    loggerTour.info(f"The tournament is over. ID: {tournamentID}")
                    users_mess_list = ""
                    for team in self.team_list:
                        users_mess_list += f"Team {team.username}\n"
                        for teammate in team.teammates:
                            users_mess_list += f"{teammate.username} ({teammate.elo} TRP)\n"
                        users_mess_list += "\n"

                    message = {
                        "title": "📋 Tournament is over! Updated rating:",
                        "description": users_mess_list,
                    }

                    self.discord_sender(message)

        except ValueError as ex:
            loggerTour.error(ex.args[0])
        except Exception as ex:
            loggerTour.error(f"Tournament with URL: {tournament_url} not found. ERROR: {ex}")

    def initialize_match(self, teams=None):
        loggerTour.debug(self.tournament_url)
        loggerTour.info("Start application")
        challonge.set_credentials(os.getenv('CHALLONGE_LOGIN'), os.getenv('CHALLONGE_API_KEY'))
        self.start_polling(self.tournament_url, teams)

    def get_value_or_env(self, value, env_var_name):
        if value is None:
            try:
                value = os.getenv(env_var_name)
            except AttributeError:
                loggerTour.error(f"It failed to retrieve the value for {env_var_name} from the environment.")
        return value
