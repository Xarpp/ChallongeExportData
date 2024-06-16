from time import sleep
from DiscordBot import *
import argparse
import challonge
from GoogleSheetsManager import *
from Users import *
import os
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(os.path.basename(__file__))


googleSheetsManager = GoogleSheetsManager(os.getenv("SPREADSHEET_ID"), os.getenv("RANGE_NAME"))
users_list = []
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
        users_list.append(User(username=user_item[0], elo=int(user_item[1]), calibration=int(user_item[2])))
        logger.debug(f'New User object has been created. Username - {user_item[0]}. ELO - {user_item[1]}. Calibration - {user_item[2]}')


def check_users_in_sheet(participants):
    for participant in participants:
        existing_user = next((user for user in users_list if user.username == participant['name']), None)

        if not existing_user:
            new_user = User(username=participant['name'], elo=1000, calibration=10, id=participant['id'])
            googleSheetsManager.add_new_user(new_user)
            users_list.append(new_user)
            logger.debug(f'Created new user. Username - {new_user.username}. ELO - {new_user.elo}. '
                         f'Calibration - {new_user.calibration}')
        else:
            existing_user.id = participant['id']
            logger.debug(f'User {existing_user.username} already exists.')


def get_tournament_user_list():
    logger.debug("Getting a list of tournament players")
    message = ""
    for user in users_list:
        message += f"{user.username} - {user.elo}\n"
    logger.debug("List of tournament players created successfully")
    return message


def discord_sender(message):
    logger.debug("Sending message to Discord Channel")
    send_message(message)
    logger.debug("Message sent successfully")


def change_elo_in_sheets(players):
    logger.debug("Updating ELO for players")
    for player in players:
        googleSheetsManager.update_elo_by_username(player)


def calculate_elo(match):
    logger.debug(f'Calculating ELO for matchID - {match["id"]}')
    player1 = get_user_by_id(match['player1_id'])
    player2 = get_user_by_id(match['player2_id'])

    K1 = K2 = 50

    if player1.calibration > 0:
        K1 = 200
        player1.calibration -= 1

    if player2.calibration > 0:
        K2 = 200
        player2.calibration -= 1

    SA1 = 1 if player1.id == match['winner_id'] else 0
    EA1 = 1 / (1 + pow(10, (player2.elo - player1.elo) / 400))

    SA2 = 1 if player2.id == match['winner_id'] else 0
    EA2 = 1 / (1 + pow(10, (player1.elo - player2.elo) / 400))

    player1.elo += int(K1 * (SA1 - EA1))
    player2.elo += int(K2 * (SA2 - EA2))

    logger.debug(f'Player1: K: {K1}, SA: {SA1}, EA: {EA1}')
    logger.debug(f'Player2: K: {K2}, SA: {SA2}, EA: {EA2}')

    change_elo_in_sheets([player1, player2])

    return player1, player2


def process_matches(current_matches):
    logger.debug("Checking new matches")
    for match in current_matches:
        if match['id'] not in sent_messages:
            if match['state'] == 'open':

                player1 = get_user_by_id(match['player1_id'])
                player2 = get_user_by_id(match['player2_id'])

                logger.debug(f"New match has started. ID: {match['id']}. Player1: {player1.username}. "
                             f"Player2: {player2.username}")

                discord_sender(f"Новый матч:\n{player1.username} VS {player2.username}")

                sent_messages[match['id']] = 'open'
        elif match['state'] == 'complete':
            if sent_messages.get(match['id']) == 'open':
                players = calculate_elo(match)

                logger.debug(f"Match is over. ID: {match['id']}. Player1: {players[0].username}. "
                             f"Player2: {players[1].username}")

                discord_sender(f"Завершенный матч:\n{players[0].username} - {players[0].elo} VS {players[1].username} - {players[1].elo}")
                sent_messages[match['id']] = 'complete'


def start_polling(tournament_url):
    try:
        logger.debug("Processing of the tournament has start")
        tournament = challonge.tournaments.show(tournament_url)
        tournamentID = tournament["id"]
        state = tournament["state"]

        if state != "complete'":
            parse_users_from_sheets()
            check_users_in_sheet(challonge.participants.index(tournamentID))
            discord_sender(get_tournament_user_list())

            while state == "pending":
                logger.debug("Waiting for the start of the tournament...")
                state = challonge.tournaments.show(tournamentID)['state']
                sleep(2)

            logger.debug(f"Tournament has start. ID: {tournamentID}")
            while state != 'complete':
                matches = challonge.matches.index(tournamentID)
                process_matches(matches)
                state = challonge.tournaments.show(tournamentID)['state']
                sleep(2)

        logger.debug(f"The tournament is over. ID: {tournamentID}")
        discord_sender("Турнир завершен")
        discord_sender(get_tournament_user_list())
    except ValueError as ex:
        logger.error(ex.args[0])
    except Exception as ex:
        logger.error(f"Tournament with URL: {tournament_url} not found. ERROR: {ex}")



if __name__ == "__main__":
    logger.debug("Start application")
    challonge.set_credentials(os.getenv('CHALLONGE_LOGIN'), os.getenv('CHALLONGE_API_KEY'))

    parser = argparse.ArgumentParser(description='Tournament Link Parser.')

    parser.add_argument('--url', type=str, help='Tournament URL')
    args = parser.parse_args()

    if args.url is not None:
        start_polling(args.url)
    else:
        logger.error("Tournament URL was not entered")
