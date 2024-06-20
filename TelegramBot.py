import asyncio
import os
import subprocess
import sys
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from aiogram import Bot, Dispatcher, Router, F
from dotenv import load_dotenv, find_dotenv
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, parse_mode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile,
)

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
    finish = State()


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
    await bot.send_photo(chat_id=message.chat.id, photo=photo, caption="Type the *Webhook link* of the Discord tournament room:",
                         parse_mode="MarkdownV2", reply_markup=ReplyKeyboardRemove())


@form_router.message(Settings.webhook_url)
async def process_webhook_url(message: Message, state: FSMContext) -> None:
    data = await state.update_data(webhook_url=message.text)
    await state.set_state(Settings.finish)
    await message.answer(f"Double-check the data:\nID: {data['url']}\nGoogle Sheet page: {data['sheet_list']}\n"
                         f"Webhook link: {data['webhook_url']}",
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[
                                 [
                                     KeyboardButton(text="Start"),
                                     KeyboardButton(text="Сancel")
                                 ]
                             ]
                         ), resize_keyboard=True),


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

    load_dotenv(find_dotenv(), verbose=True, override=True)
    subprocess.run([python_executable, script_path])


@form_router.message(Settings.finish)
async def process_finish(message: Message, state: FSMContext) -> None:
    data = await state.update_data(finish=message.text)
    await state.clear()
    if data['finish'] == "Start":
        await message.answer("You can run a tournament on Challounge", reply_markup=ReplyKeyboardRemove())
        prepare_tournament(data)
    else:
        await message.answer("Start is canceled, to re\-enter send */start\_tournament* again",
                             reply_markup=ReplyKeyboardRemove(),  parse_mode="MarkdownV2")


async def start_bot():
    await dp.start_polling(bot)


@form_router.message(Command("cancell"))
@form_router.message(F.text.casefold() == "cancell")
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
