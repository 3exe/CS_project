import asyncio
import base64
import email
import imaplib
import logging
import os
import random
import re
import string
import time
import datetime
import sqlite3

import aiofiles
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram import Router, F
from aiogram.filters import Text
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
# from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import hlink

# import aiosqlite

from config_reader import config

from faker import Faker
from pyppeteer import launch
from pyppeteer.errors import TimeoutError

faker = Faker()

logging.basicConfig(level=logging.INFO)


#####################################################################################################################
#                                                                                                                   #
#    ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ  #
#                                                                                                                   #
#####################################################################################################################

def generate_session_storage(length=10):
    # Generate a random alphanumeric string of given length
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


session_storage = generate_session_storage()


def generate_local_storage(length=10):
    # Generate a random alphanumeric string of given length
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


local_storage = generate_local_storage()


def generate_open_db():
    db_name = ''.join(random.choices(string.ascii_lowercase, k=8))
    db_version = random.randint(1, 100)
    display_name = ''.join(random.choices(string.ascii_lowercase, k=8))
    estimated_size = random.randint(1, 1000) * 1024 * 1024
    return f"{db_name}::{db_version}::{display_name}::{estimated_size}"


print(generate_open_db())


def generate_fingerprint():
    components = [
        "User-Agent",
        "language",
        "colorDepth",
        "deviceMemory",
        "hardwareConcurrency",
        "screenResolution",
        "availableScreenResolution",
        "timezoneOffset",
        "timezone",
        "sessionStorage",
        "localStorage",
        "indexedDb",
        "addBehavior",
        "openDatabase",
        "cpuClass",
        "platform",
        "doNotTrack",
        "plugins",
        "canvas",
        "webgl",
        "webglVendorAndRenderer",
        "adBlock",
        "hasLiedLanguages",
        "hasLiedResolution",
        "hasLiedOs",
        "hasLiedBrowser",
        "touchSupport",
        "fonts",
        "audio"
    ]
    fingerprint = {}
    for component in components:
        if component == "User-Agent":
            fingerprint[component] = faker.user_agent()
        elif component in ["screenResolution", "availableScreenResolution"]:
            width = random.randint(1024, 1920)
            height = random.randint(768, 1080)
            fingerprint[component] = f"{width}x{height}"
        elif component == "timezone":
            fingerprint[component] = faker.timezone()
        elif component == "sessionStorage":
            fingerprint[component] = session_storage
        elif component == "localStorage":
            fingerprint[component] = local_storage
        elif component == "indexedDb":
            fingerprint[component] = "IDBFactory, IDBKeyRange, indexedDB.open"
        elif component == "addBehavior":
            fingerprint[component] = str(random.choice([True, False]))
        elif component == "openDatabase":
            fingerprint[component] = generate_open_db()
        elif component == "doNotTrack":
            fingerprint[component] = str(random.choice([None, "1", "Unspecified"]))
        elif component in ["webglVendorAndRenderer", "canvas"]:
            fingerprint[component] = faker.sha256()
        elif component == "audio":
            fingerprint[component] = faker.sha256()
        elif component == "language":
            fingerprint[component] = "en-US"
        elif component == "colorDepth":
            fingerprint[component] = "24"
        elif component == "deviceMemory":
            fingerprint[component] = "16"
        else:
            fingerprint[component] = str(random.randint(0, 99999999))
    return fingerprint


print(generate_fingerprint())

fp = generate_fingerprint()

key_capcha = config.rucapcha_token.get_secret_value()
#####################################################################################################################
#                                                                                                                   #
#    ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ ПЕРЕДЕЛАТЬ  #
#                                                                                                                   #
#####################################################################################################################


# скачиваем капчу
async def download_file(url: str, file_path: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await resp.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
            else:
                print(f'Error downloading file: {resp.status}')


# преобразуем файл капчи в base64
async def encode_image_to_base64(filename):
    with open(filename, 'rb') as file:
        image_data = file.read()
    encoded_data = base64.b64encode(image_data)
    os.remove(filename)
    return encoded_data.decode('utf-8')


# решаем капчу
async def rucapcha(base64_data):
    url = 'http://rucaptcha.com/in.php'
    method = 'base64'

    params = {'key': key_capcha, 'method': method, 'body': base64_data, 'json': 1}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=params) as resp:
            response_text = await resp.json()
            return response_text


# получаем решение
async def res_rucapcha(id_capcha):
    url = 'http://rucaptcha.com/res.php'
    action = 'get'

    params = {'key': key_capcha, 'id': id_capcha, 'action': action, 'json': 1}

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.post(url, data=params) as resp:
                response_text = await resp.json()
                if response_text['status'] == 1:
                    return response_text['request']
                elif response_text['status'] == 0:
                    await asyncio.sleep(3)
                else:
                    return 0


# получаем первую строку из текстовика с почтами
async def get_first_email_line(filename):
    async with aiofiles.open(filename, 'r+') as f:
        lines = await f.readlines()
        first_line = lines[0]
        await f.seek(0)
        await f.writelines(lines[1:])
        await f.truncate()
    return first_line.strip().split(':')


# получаем последнее письмо из почты
async def get_latest_email(login, password):
    mail = imaplib.IMAP4_SSL('imap.rambler.ru')
    mail.login(login, password)
    mail.select('inbox')

    for i in range(10):
        print(f'попытка номер: {i + 1}')
        status, data = mail.search(None, 'ALL')
        mail_ids = data[0].split()
        latest_email_id = mail_ids[-1]

        status, data = mail.fetch(latest_email_id, "(RFC822)")
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)

        sender = email.utils.parseaddr(email_message['From'])[1]
        print(sender)
        if sender == 'info@ruvds.com':
            mail.close()
            mail.logout()
            return email_message.get_payload(decode=True)

        await asyncio.sleep(10)

    else:
        mail.close()
        mail.logout()
        return None


# получаем токен RuVds
async def handle_request(req, page, future):
    if str(req.url).startswith("https://ruvds.com/user_AddOrUpdate.h?fName=_auth.reg"):
        response = await page.waitForResponse(req.url)
        text = await response.text()
        output = re.search(r"id:'(.*?)',firstName", str(text))
        if output and output.group(1):
            future.set_result(output.group(1))
    else:
        return 0


# генерация соли
async def generate_r():
    return random.randint(100000000, 999999999)


# генерация рандомного пароля
async def generate_random_password(length):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))


# случайное имя
async def generate_random_first_name():
    names = ['Григорий', 'Лев', 'Андрей', 'Роман', 'Арсений', 'Степан', 'Владислав', 'Никита', 'Глеб',
             'Марк', 'Давид', 'Ярослав', 'Евгений', 'Матвей', 'Фёдор', 'Николай', 'Алексей', 'Андрей', 'Артемий',
             'Виктор', 'Никита', 'Даниил', 'Денис', 'Егор', 'Игорь', 'Лев', 'Леонид', 'Павел', 'Петр', 'Роман',
             'Руслан', 'Сергей', 'Семён', 'Тимофей']
    return random.choice(names)


# случайная фамилия
async def generate_random_last_name():
    surnames = ['Иванов', 'Смирнов', 'Кузнецов', 'Попов', 'Васильев', 'Петров', 'Соколов', 'Михайлов', 'Новиков',
                'Федоров', 'Морозов', 'Волков', 'Алексеев', 'Лебедев', 'Семенов', 'Егоров', 'Павлов', 'Козлов',
                'Степанов', 'Николаев', 'Орлов', 'Андреев', 'Макаров', 'Никитин', 'Захаров', 'Зайцев', 'Соловьев',
                'Борисов', 'Яковлев', 'Григорьев', 'Романов', 'Воробьев', 'Сергеев', 'Кузьмин', 'Фролов']
    return random.choice(surnames)


# смена пароля от аккаунта RuVds (обязательная процедура перед регистрацией)
async def change_pass(login, password, final_id, eml_password):
    result_task = asyncio.create_task(generate_r())
    r = await result_task

    url = f'https://ruvds.com/user_ChangePassword.h?fName=_auth.changePassword._result&r={r}'
    data = {
        "userId": final_id,
        "email": login,
        "p": password,
        "newPassword": eml_password
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            return await response.text()


# добавления имени, фамилии и номера телефона в аккаунт (обязательно для использования тестового периода)
async def add_data(eml_password, final_id, login):
    result_task = asyncio.create_task(generate_r())
    result_task2 = asyncio.create_task(generate_random_first_name())
    result_task3 = asyncio.create_task(generate_random_last_name())

    r = await result_task
    name = await result_task2
    surname = await result_task3

    url = f'https://ruvds.com/user_AddOrUpdate.h?fName=jm.Data["PersonalPage"]._saveResult&r={r}'
    data = {
        "p": eml_password,
        "id": final_id,
        "firstName": name,
        "lastName": surname,
        "countryId": "178",
        "city": "Санкт-Петербург",
        "email": login,
        "privacyPolicyAccepted": "true"
    }
    print(url, data)
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            return await response.text()


async def get_request_data():
    future = asyncio.Future()

    browser = await launch(headless=False, args=['--no-sandbox'])

    page = await browser.newPage()
    await page.setViewport({'width': random.randint(1024, 1920), 'height': random.randint(768, 1080)})  # ###########
    await page.setExtraHTTPHeaders(fp)

    await page.goto('https://ruvds.com/ru-rub')
    await asyncio.sleep(2)
    # Кликаем по кнопке и ждем запроса
    await asyncio.gather(
        page.waitForSelector('#auth_registerButton'),
        page.click('#auth_registerButton')

    )
    src = await page.querySelectorEval('.ttb', 'el => el.getAttribute("src")')
    # скачиваем капчу
    file_path = f'file{random.randint(0, 9999999)}.jpg'  # #####################
    await download_file('https://ruvds.com/' + src, file_path)

    # преобразуем файл капчи в base64
    result_task = asyncio.create_task(encode_image_to_base64(file_path))
    base64_data = await result_task

    result = await rucapcha(base64_data)
    print(result)

    status = result['status']
    id_capcha = result['request']
    if status != 1:
        return 0

    result_capcha = await res_rucapcha(id_capcha)

    # вводим решение капчи
    await page.waitForSelector('#auth_RegCodeTB_div_tb')
    input_field = await page.querySelector('#auth_RegCodeTB_div_tb')
    # Вводим текст в поле input
    await input_field.type(result_capcha)

    # получаем логин и пароль от почты из файла.тхт
    result_task = asyncio.create_task(get_first_email_line('mail.txt'))
    login, eml_password = await result_task

    await page.waitForSelector('#auth_RegEmail_div_tb')
    input_field = await page.querySelector('#auth_RegEmail_div_tb')
    # Вводим текст в поле input
    await input_field.type(login)

    await asyncio.sleep(2)

    # клик по соглашению
    await asyncio.gather(
        page.waitForSelector('#auth_PrivacyPolicy_input'),
        page.click('#auth_PrivacyPolicy_input')

    )

    await asyncio.sleep(2)

    # подрубаем перехват запросов
    await page.setRequestInterception(True)

    page.on('request', lambda req: asyncio.ensure_future(handle_request(req, page, future)))

    # клик по кнопке реги
    await asyncio.gather(
        page.waitForSelector('#auth_Reg_btn'),
        page.click('#auth_Reg_btn')

    )
    # вырубаем
    await page.setRequestInterception(False)

    await future

    # Получение результата
    final_id = future.result()
    print(final_id)

    try:
        # Ожидание СООБЩЕНИЯ ОБ УСПЕШНОЙ РЕГИСТРАЦИИ
        await page.waitForSelector('#regSuccess_wnd_div', timeout=5000)
        # await browser.close()
        latest_email = await get_latest_email(login, eml_password)
        if latest_email:
            unicode_string = latest_email.decode('utf-8')
            match = re.search(r'Ваш пароль:</span> <strong>.*</', unicode_string)  # \s*(.*?)\s*

            if match:
                vds_password = match.group(1)
                print(vds_password)

                new_password = await change_pass(login, vds_password, final_id, eml_password)

                print(new_password)
                print(await add_data(eml_password, final_id, login))

        else:
            print("Возникли проблемы на этапе получения письма. попробуйте снова...")

    except TimeoutError:
        # Если элемент не найден, выводим сообщение об ошибке
        print('Element not found!')


#

time_to_top_up = 1

yoo_token = 'Bearer ' + config.yoo_token.get_secret_value()

bot = Bot(token=config.bot_token.get_secret_value(), parse_mode='HTML')
dp = Dispatcher()

#

db = sqlite3.connect("users.db")
cur = db.cursor()
router = Router()


class AddBalance(StatesGroup):
    choosing_payment_type = State()
    choosing_sum = State()
    check_transaction = State()


class ChoosingGoods(StatesGroup):
    choosing_goods = State()


async def wallet():
    return '4100116997512588'


async def user_profile(message):
    buttons = [
        [
            types.KeyboardButton(text="Пополнить баланс")
        ],
        [
            types.KeyboardButton(text="Назад"),
            types.KeyboardButton(text="Список покупок")
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )
    user_id = message.from_user.id

    balance = await asyncio.create_task(get_balance(user_id))

    profile_message = f'Вы перешли в профиль.\nВаш id: {user_id}\nВаш баланс: {balance} руб.'
    await message.answer(profile_message, reply_markup=keyboard)


async def main_menu(message):
    user_full_name = message.from_user.full_name
    buttons = [
        [
            types.KeyboardButton(text="Купить")
        ],
        [
            types.KeyboardButton(text="Профиль"),
            types.KeyboardButton(text="Поддержка")
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )
    await message.answer(f"Привет, {user_full_name}!", reply_markup=keyboard)


# получаем баланс пользователя
async def get_balance(user_id):
    balance = cur.execute(f"SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchall()[0][0]
    return balance


async def generate_comment(length=15):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    # user_name = message.from_user.first_name
    user_full_name = message.from_user.full_name
    logging.info(f'{user_id} {user_full_name} {time.asctime()}')

    await state.clear()

    await main_menu(message)

    command = "INSERT INTO users (user_id) VALUES(?)"
    cur.execute(command, (user_id, ))
    db.commit()

    # await message.reply("Запуск!")
    # result_task = await asyncio.create_task(get_request_data())


@dp.message(Text("Назад"))
async def cmd_start(message: types.Message, state: FSMContext):

    await state.clear()
    await main_menu(message)


available_payment_type = ["Из кошелька ЮMoney", "С банковской карты"]
check_transaction_buttons = ["Я оплатил/а", "Отмена оплаты"]


@dp.message(AddBalance.choosing_payment_type, F.text.in_(available_payment_type))
async def payment_type_chosen(message: Message, state: FSMContext):
    await state.update_data(chosen_type=message.text.lower())
    await message.answer(
        text="Введите сумму пополнения:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddBalance.choosing_sum)


@dp.message(AddBalance.choosing_payment_type)
async def payment_type_chosen_incorrectly(message: Message):
    await message.answer(
        text="Я не знаю такого способа оплаты.\n"
             "Пожалуйста, выберите из списка ниже:"
    )


async def wait_add_balance(message):
    await asyncio.sleep(time_to_top_up * 60)

    user_id = message.from_user.id
    flag = cur.execute(f"SELECT paid_flag FROM users WHERE user_id = ?", (user_id, )).fetchall()[0][0]

    if flag:
        command = "UPDATE users SET payment_info = ? WHERE user_id = ?"
        cur.execute(command, (None, message.from_user.id))
        db.commit()

        await message.answer(text="Время на оплату вышло!")


@dp.message(ChoosingGoods.choosing_goods)
async def pay(message: Message, state: FSMContext):
    cur.execute("SELECT title, price FROM goods")
    rows = cur.fetchall()

    goods = []
    for row in rows:
        text = f"{row[0]} | {row[1]} руб."
        goods.append(text)

    if message.text in goods:
        buttons = [[types.KeyboardButton(text="Подтвердить покупку"), ],
                   [types.KeyboardButton(text="Назад")], ]

        keyboard = types.ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
        )

        title = message.text.split(' | ')[0]
        data = cur.execute(f"SELECT * FROM goods WHERE title = ?", (title, )).fetchall()[0]
        await message.answer(text=f'<b>Наименование товара:</b> {data[1]}\n'
                                  f'<b>Цена:</b> {data[2]}\n<b>Описание:</b>\n{data[3]}', reply_markup=keyboard)


@dp.message(AddBalance.choosing_sum)
async def add_balance(message: Message, state: FSMContext):
    user_data = await state.get_data()
    try:
        add_sum = float(message.text) * 1
        add_sum = abs(round(add_sum, 1))

        if add_sum < 10.0 or add_sum > 5000.0:
            await message.answer(text=f"Сумма должна быть больше 10 и меньше 5000 !!1")
            return

        buttons = [
            [
                types.KeyboardButton(text="Я оплатил/а"),
                types.KeyboardButton(text="Отмена оплаты")
            ],
        ]
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
        )

        comment = await generate_comment()

        payment_type = 'PC' if user_data['chosen_type'] == "из кошелька юmoney" else 'AC'

        kom = 0.03
        if payment_type == 'PC':
            kom = 0.01

        yoo_sum = add_sum + (add_sum * kom)
        add_balance_link = f'https://yoomoney.ru/quickpay/confirm.xml?receiver={await wallet()}&quickpay-form=button' \
                           f'&paymentType={payment_type}&sum={yoo_sum}' \
                           f'&successURL=https://t.me/dedikfree_bot&label={comment}'

        payment_info = f'{add_sum} {comment}'
        user_id = message.from_user.id
        command = "UPDATE users SET payment_info = ?, paid_flag = ? WHERE user_id = ?"
        cur.execute(command, (payment_info, 1, user_id))
        db.commit()

        await message.answer(
            text=f"<b>Вы пополняете баланс на: {add_sum} рублей.\nМетод оплаты: {user_data['chosen_type']}.\n</b>"
                 f"Для оплаты перейдите по {hlink('ссылке', add_balance_link)}\n"
                 f"На оплату у Вас <b>{time_to_top_up} минут.</b>",
            reply_markup=keyboard,
        )

        # сброс состояния и сохранённых данных у пользователя
        await state.clear()

        asyncio.create_task(wait_add_balance(message))
        await state.set_state(AddBalance.check_transaction)

    except ValueError:
        await message.answer(
            text=f"попробуй еще раз"
        )


async def yoo_check():
    headers = {
        "Authorization": yoo_token,
    }

    date = datetime.datetime.now() - datetime.timedelta(minutes=time_to_top_up)
    date = date.isoformat()
    params = {
        "type": "deposition",
        "response_type": "code",
        "redirect_uri": "https://www.blessed.tk",
        "scope": "account-info operation-history",
        "from": date,

    }

    url = 'https://yoomoney.ru/api/operation-history'

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=params, headers=headers) as resp:
            response_text = await resp.json()
            return response_text["operations"]


@dp.message(AddBalance.check_transaction, Text(check_transaction_buttons[0]))
async def add_balance(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = cur.execute(f"SELECT payment_info FROM users WHERE user_id = ?", (user_id,)).fetchall()[0][0]
    balance = await get_balance(user_id)

    if data:
        data = data.split()
        await message.answer(text=f"{data}")

        result_list = await yoo_check()

        for i in result_list:
            amount = float(round(i["amount"], 1))
            label = i["label"]

            if float(data[0]) == amount and data[1] == label:
                await state.clear()
                command = "UPDATE users SET balance = ?, paid_flag = ? WHERE user_id = ?"
                cur.execute(command, (round(amount + balance, 1), 0, user_id))
                db.commit()
                await message.answer(text=f"На ваш баланс зачислено {amount} рублей !!1")
                await main_menu(message)
                return
        else:
            await message.answer(text=f"Пополнение не найдено")

    else:
        await message.answer(text=f"Время на оплату вышло!!1")
        await state.clear()
        await main_menu(message)


@dp.message(AddBalance.check_transaction, Text(check_transaction_buttons[1]))
async def add_balance(message: Message, state: FSMContext):
    command = "UPDATE users SET payment_info = ?, paid_flag = ? WHERE user_id = ?"
    cur.execute(command, (None, 0, message.from_user.id))
    db.commit()

    await state.clear()
    await main_menu(message)


@dp.message(AddBalance.check_transaction)
async def add_balance(message: Message):
    await message.answer(text=f"ватафак")


@dp.message(Text("Пополнить баланс"))
async def add_balance(message: Message, state: FSMContext):
    buttons = [
        [
            types.KeyboardButton(text="Из кошелька ЮMoney"),
            types.KeyboardButton(text="С банковской карты")
        ],
        [
            types.KeyboardButton(text="Назад"),
        ],
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )

    await message.answer(
        text="Выберите метод оплаты:",
        reply_markup=keyboard
    )
    # Устанавливаем пользователю состояние
    await state.set_state(AddBalance.choosing_payment_type)


@dp.message(Text("Поддержка"))
async def helping(message: types.Message):
    await message.answer("По всем вопросам @root112")


@dp.message(Text("Профиль"))
async def profile(message: types.Message):
    await user_profile(message)


@dp.message(Text("Список покупок"))
async def goods_list(message: types.Message):
    user_id = message.from_user.id

    data = cur.execute(f"SELECT shop_list FROM users WHERE user_id = ?", (user_id,)).fetchall()[0][0]

    if data:
        pass                                                                # ТУТ СПИСОК ПОКУПОК
    else:
        await message.answer(text=f"У Вас нет покупок...")


@dp.message(Text("Купить"))
async def buy(message: types.Message, state: FSMContext):
    cur.execute("SELECT title, price FROM goods")
    rows = cur.fetchall()

    buttons = []
    for row in rows:
        text = f"{row[0]} | {row[1]} руб."
        product = [
            types.KeyboardButton(text=text),
        ]
        buttons.append(product)
    buttons.append([types.KeyboardButton(text=f"Назад"), ])
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите товар"
    )

    await state.set_state(ChoosingGoods.choosing_goods)
    await message.answer(f"Выберите товар:", reply_markup=keyboard)


async def main():
    # Запускаем бота и пропускаем все накопленные входящие
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    # asyncio.run(get_request_data())
