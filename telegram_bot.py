import asyncio
import os
import sys

import challonge as challonge_tg
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from aiogram import Bot, Dispatcher, Router, F
from dotenv import load_dotenv, find_dotenv
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile,
)

from tournament_start import Tournament

load_dotenv(find_dotenv(), verbose=True, override=True)

TOKEN = os.getenv("BOT_TG_TOKEN")

form_router = Router()

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(form_router)
python_executable = sys.executable

script_path = 'tournament_start.py'


class Settings(StatesGroup):
    url = State()
    sheet_list = State()
    webhook_url = State()
    format = State()
    finish = State()
    teams = State()


def prepare_tournament(data):
    variables_to_update = {
        'TOURNAMENT_URL': '\"' + data['url'] + '\"',
        'SHEET_LIST': '\"' + data['sheet_list'] + '\"',
        'DISCORD_WEBHOOK_URL': '\"' + data['webhook_url'] + '\"'
    }

    with open('.env', 'r+') as file:
        lines = file.readlines()
        for var, new_value in variables_to_update.items():
            for i, line in enumerate(lines):
                if line.startswith(var + '='):
                    lines[i] = f'{var}={new_value}\n'
                    break
            else:
                lines.append(f'{var}={new_value}\n')

        file.seek(0)
        file.writelines(lines)
        file.truncate()


@form_router.message(Command("start_tournament"))
async def command_start(message: Message, state: FSMContext) -> None:
    photo = FSInputFile("images/image1.png")
    await state.set_state(Settings.url)
    await bot.send_photo(chat_id=message.chat.id, photo=photo, caption="Type the tournament *ID:*",
                         parse_mode="MarkdownV2", reply_markup=ReplyKeyboardRemove())


@form_router.message(Settings.url)
async def process_url(message: Message, state: FSMContext) -> None:
    photo = FSInputFile("images/image3.png")
    await state.update_data(url=message.text)
    await state.set_state(Settings.sheet_list)
    await bot.send_photo(chat_id=message.chat.id, photo=photo, caption="Type the *name of the Google Sheets:*",
                         parse_mode="MarkdownV2", reply_markup=ReplyKeyboardRemove())


@form_router.message(Settings.sheet_list)
async def process_sheet_list(message: Message, state: FSMContext) -> None:
    photo = FSInputFile("images/image2.png")

    await state.update_data(sheet_list=message.text)
    await state.set_state(Settings.webhook_url)
    await bot.send_photo(chat_id=message.chat.id, photo=photo,
                         caption="Type the *Webhook link* of the Discord tournament room:",
                         parse_mode="MarkdownV2", reply_markup=ReplyKeyboardRemove())


@form_router.message(Settings.webhook_url)
async def process_webhook_url(message: Message, state: FSMContext) -> None:
    await state.update_data(webhook_url=message.text)
    await state.set_state(Settings.format)

    await message.answer("What is the format of the tournament?", reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="1x1"),
                KeyboardButton(text="2x2"),
                KeyboardButton(text="5x5")
            ]
        ]
    ), resize_keyboard=True)


@form_router.message(Settings.format)
async def process_format(message: Message, state: FSMContext) -> None:
    data = await state.update_data(format=message.text)
    if data["format"] == "1x1":
        await message.answer(f"Double-check the data:\nID: {data['url']}\nGoogle Sheet page: {data['sheet_list']}\n"
                             f"Webhook link: {data['webhook_url']}",
                             reply_markup=ReplyKeyboardMarkup(
                                 keyboard=[
                                     [
                                         KeyboardButton(text="Start"),
                                         KeyboardButton(text="Сancel")
                                     ]
                                 ]
                             ), resize_keyboard=True)
        await state.set_state(Settings.finish)
    elif data["format"] == "2x2" or data["format"] == "5x5":
        challonge_tg.set_credentials(os.getenv('CHALLONGE_LOGIN'), os.getenv('CHALLONGE_API_KEY'))
        teams = {}
        teams_to_request = []
        mess = ""
        participants = challonge_tg.participants.index(data['url'])
        for participant in participants:
            name = participant["name"]
            if name not in teams_to_request:
                teams_to_request.append(name)
                mess += name + "\n"
        await message.answer(f"Found {len(teams_to_request)} teams:\n{mess}")

        await state.update_data(teams_to_request=teams_to_request)
        await state.update_data(teams=teams)
        await state.update_data(team_count=2 if data["format"] == "2x2" else 5 if data["format"] == "5x5" else None)
        await request_teams(message.from_user.id, state)


async def request_teams(user_id, state: FSMContext):
    data = await state.get_data()

    teams_to_request = data["teams_to_request"]
    if teams_to_request:
        await state.set_state(Settings.teams)
        team = teams_to_request[0]
        await bot.send_message(user_id, f"Enter the members of the {team} team:",
                               reply_markup=ReplyKeyboardRemove())
    else:
        message = ""
        for team_name, players in data["teams"].items():
            message += f"▶️Team: {team_name}\n"
            message += "Participants: " + ", ".join(players) + "\n\n"
        await state.set_state(Settings.finish)
        await bot.send_message(user_id,
                               f"Double-check the data:\nID: {data['url']}\nGoogle Sheet page: {data['sheet_list']}\n"
                               f"Webhook link: {data['webhook_url']}\n\n{message} ",
                               reply_markup=ReplyKeyboardMarkup(
                                   keyboard=[
                                       [
                                           KeyboardButton(text="Start"),
                                           KeyboardButton(text="Cancel")
                                       ]
                                   ]
                               ))


@form_router.message(Settings.teams)
async def process_teams(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    participants = message.text.split("\n")

    if len(participants) != int(data["team_count"]):
        await message.answer("The wrong number of participants was entered, try again",
                             reply_markup=ReplyKeyboardRemove())

    else:
        team = data["teams_to_request"].pop(0)
        data["teams"][team] = participants
        await state.update_data(data)

    await request_teams(message.from_user.id, state)


@form_router.message(Settings.finish)
async def process_finish(message: Message, state: FSMContext) -> None:
    data = await state.update_data(finish=message.text)
    await state.clear()
    if data['finish'] == "Start":
        await message.answer("You can run a tournament on Challounge", reply_markup=ReplyKeyboardRemove())
        prepare_tournament(data)
        tournament = Tournament()
        if data['format'] == "1x1":
            tournament.initialize_match()
        elif data['format'] == "2x2" or data['format'] == "5x5":
            tournament.initialize_match(data["teams"])
    else:
        await message.answer("Start is canceled, to re\-enter send */start\_tournament* again",
                             reply_markup=ReplyKeyboardRemove(), parse_mode="MarkdownV2")


async def start_bot():
    await dp.start_polling(bot)


@form_router.message(Command("cancel"))
@form_router.message(F.text.casefold() == "cancel")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer(
        "Start is canceled",
        reply_markup=ReplyKeyboardRemove(),
    )


@form_router.message(CommandStart)
async def command_start(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "Hi, this is a bot to synchronize a tournament with Discord channel and Google Sheets\\.\n"
            "Write */start\_tournament* to start a tournament", parse_mode="MarkdownV2")


if __name__ == "__main__":
    asyncio.run(start_bot())
