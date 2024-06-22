from time import sleep
from discord_bot import *
import argparse
import challonge
from google_sheets_manager import *
from users import *
import os
from dotenv import load_dotenv, find_dotenv

logger = get_logger(os.path.basename(__file__))

load_dotenv(find_dotenv(), verbose=True, override=True)

googleSheetsManager = GoogleSheetsManager(os.getenv("SHEET_ID"), os.getenv("SHEET_LIST") + "!" +
                                          os.getenv("SHEET_RANGE"))
users_list = []
all_users_from_sheets = []
sent_messages = {}


def get_user_by_id(id):
    logger.debug("Getting user by id")
    for item in users_list:
        if item.id == id:
            logger.debug("User was successfully found")
            return item
    logger.error(f'User with id - {id} was not found')
    return None


def parse_users_from_sheets():
    logger.debug("Parsing user's from sheets")
    users_sheets = googleSheetsManager.get_users_data()
    if not users_sheets:
        return
    for user_item in users_sheets:
        if not user_item:
            continue
        all_users_from_sheets.append(User(username=user_item[0], elo=int(user_item[1]), calibration=int(user_item[2]),
                                          matches_played=int(user_item[3]), matches_won=int(user_item[4]),
                                          tournaments_played=int(user_item[5])))
        logger.debug(
            f'New User object has been created. Username - {user_item[0]}. ELO - {user_item[1]}. '
            f'Calibration - {user_item[2]}')


def check_users_in_sheet(participants):
    for participant in participants:
        existing_user = next((user for user in all_users_from_sheets if user.username == participant['name']), None)

        if not existing_user:
            new_user = User(username=participant['name'], elo=1000, calibration=10, id=participant['id'])
            googleSheetsManager.add_new_user(new_user)
            users_list.append(new_user)
            logger.debug(f'Created new user. Username - {new_user.username}. ELO - {new_user.elo}. '
                         f'Calibration - {new_user.calibration}')
        else:
            existing_user.id = participant['id']
            existing_user.tournaments_played += 1
            users_list.append(existing_user)
            logger.debug(f'User {existing_user.username} already exists.')


def get_tournament_user_list():
    logger.debug("Getting a list of tournament players")
    message = ""
    for user in users_list:
        message += f"{user.username} ({user.elo})\n"
    logger.debug("List of tournament players created successfully")
    return message


def discord_sender(message):
    logger.debug("Sending message to Discord Channel")
    send_message(message)
    logger.debug("Message sent successfully")


def change_elo_in_sheets(players):
    logger.debug("Updating ELO for players")
    for player in players:
        googleSheetsManager.update_user_by_username(player)


def calculate_match(match):
    logger.debug(f'Calculating ELO for matchID - {match["id"]}')
    player1 = get_user_by_id(match['player1_id'])
    player2 = get_user_by_id(match['player2_id'])

    K1 = K2 = 50

    if player1.calibration > 0:
        K1 = 200

    if player2.calibration > 0:
        K2 = 200

    SA1 = 1 if player1.id == match['winner_id'] else 0
    EA1 = 1 / (1 + pow(10, (player2.elo - player1.elo) / 400))

    SA2 = 1 if player2.id == match['winner_id'] else 0
    EA2 = 1 / (1 + pow(10, (player1.elo - player2.elo) / 400))

    rating_changes1 = int(K1 * (SA1 - EA1))
    rating_changes2 = int(K2 * (SA2 - EA2))

    player1.elo += rating_changes1
    player2.elo += rating_changes2

    player1.rating_sum += rating_changes1
    player2.rating_sum += rating_changes2

    player1.matches_played += 1
    player2.matches_played += 1

    if SA1 > 0:
        player1.winner = True
        player2.winner = False
        player1.matches_won += 1
    else:
        player1.winner = False
        player2.winner = True
        player2.matches_won += 1

    logger.debug(f'Player1: K: {K1}, SA: {SA1}, EA: {EA1}')
    logger.debug(f'Player2: K: {K2}, SA: {SA2}, EA: {EA2}')

    change_elo_in_sheets([player1, player2])

    return player1, player2


def set_elo_changes(match):
    player1 = get_user_by_id(match['player1_id'])
    player2 = get_user_by_id(match['player2_id'])

    K1 = K2 = 50

    if player1.calibration > 0:
        K1 = 200
        player1.calibration -= 1

    if player2.calibration > 0:
        K2 = 200
        player2.calibration -= 1

    EA1 = 1 / (1 + pow(10, (player2.elo - player1.elo) / 400))
    EA2 = 1 / (1 + pow(10, (player1.elo - player2.elo) / 400))

    player1.r_win = int(K1 * (1 - EA1))
    player1.r_lose = int(K1 * (0 - EA1))

    player2.r_win = int(K2 * (1 - EA2))
    player2.r_lose = int(K2 * (0 - EA2))

    logger.debug(f"player1.r_win = {player1.r_win}")
    logger.debug(f"player1.r_lose = {player1.r_lose}")

    logger.debug(f"player2.r_win = {player2.r_win}")
    logger.debug(f"player2.r_lose = {player2.r_lose}")

    return player1, player2


def process_matches(current_matches):
    logger.debug("Checking new matches")
    for match in current_matches:
        if match['id'] not in sent_messages:
            if match['state'] == 'open':

                players = set_elo_changes(match)

                player1 = players[0]
                player2 = players[1]

                logger.debug(f"New match has started. ID: {match['id']}. Player1: {player1.username}. "
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

                discord_sender(message)

                sent_messages[match['id']] = 'open'
        elif match['state'] == 'complete':
            if sent_messages.get(match['id']) == 'open':
                players = calculate_match(match)

                logger.debug(f"Match is over. ID: {match['id']}. Player1: {players[0].username}. "
                             f"Player2: {players[1].username}")

                message = "🌚 Closed match: "

                if players[0].winner:
                    description = f"(W) {players[0].username} ({players[0].elo} TRP)  vs {players[1].username} ({players[1].elo} TRP)"
                else:
                    description = f"{players[0].username} ({players[0].elo} TRP)  vs (W) {players[1].username} ({players[1].elo} TRP)"
                message = {
                    "title": "🏁 Finished match",
                    "description": description,
                }

                discord_sender(message)
                sent_messages[match['id']] = 'complete'


def start_polling(tournament_url):
    try:
        logger.debug("Processing of the tournament has start")
        tournament = challonge.tournaments.show(tournament_url)
        tournamentID = tournament["id"]
        state = tournament["state"]
        logger.debug(state)

        if state != "complete":
            while state == "pending":
                logger.debug("Waiting for the start of the tournament...")
                # logger.debug(state)
                state = challonge.tournaments.show(tournamentID)['state']
                sleep(2)

            logger.debug(f"Tournament has start. ID: {tournamentID}")

            parse_users_from_sheets()
            check_users_in_sheet(challonge.participants.index(tournamentID))

            users_mess_list = ""

            for user in users_list:
                users_mess_list += f"{user.username} ({user.elo} TRP)\n"

            message = {
                "title": "📋 Tournament lineup: ",
                "description": users_mess_list,
            }

            discord_sender(message)

            while state != 'complete':
                matches = challonge.matches.index(tournamentID)
                process_matches(matches)
                state = challonge.tournaments.show(tournamentID)['state']
                sleep(2)

            logger.debug(f"The tournament is over. ID: {tournamentID}")
            users_mess_list = ""
            for user in users_list:
                users_mess_list += f"{user.username} ({user.elo} TRP)\n"

            message = {
                "title": "📋 Tournament is over! Updated rating:",
                "description": users_mess_list,
            }

            discord_sender(message)

    except ValueError as ex:
        logger.error(ex.args[0])
    except Exception as ex:
        logger.error(f"Tournament with URL: {tournament_url} not found. ERROR: {ex}")


def initialize_match(tournament_url=os.getenv("TOURNAMENT_URL")):
    logger.debug(tournament_url)

    logger.debug("Start application")
    challonge.set_credentials(os.getenv('CHALLONGE_LOGIN'), os.getenv('CHALLONGE_API_KEY'))
    start_polling(tournament_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Tournament Link Parser.')

    parser.add_argument('--url', type=str, help='Tournament URL')
    args = parser.parse_args()

    if args.url is not None:
        initialize_match(args.url)
    else:
        initialize_match()
