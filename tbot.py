import asyncio
import logging
import random
import string
import time
import datetime
import sqlite3

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram import Router, F
from aiogram.filters import Text
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message

from aiogram.utils.markdown import hlink

from config_reader import config
from ruvds import *

time_to_top_up = config.time_to_top_up  # время на пополнение в минутах

yoo_token = 'Bearer ' + config.yoo_token.get_secret_value()
wallet = config.wallet

bot = Bot(token=config.bot_token.get_secret_value(), parse_mode='HTML')
dp = Dispatcher()

available_payment_type = ["Из кошелька ЮMoney", "С банковской карты"]
check_transaction_buttons = ["Я оплатил/а", "Отмена оплаты"]

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
    submit_buy = State()


class OrderPage(StatesGroup):
    next_page = State()  # длина списка покупок (я перепутал и мне лень переназывать)
    now_page = State()


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


async def send_order(message, title, type_='default'):

    data = 'Отсутствуют'
    if type_:
        if type_.lower() == 'ru_vds':
            result = asyncio.create_task(get_request_data(message))
            r = await result

            data = r[1]
            await message.answer(data)

            if not r[0]:
                return 'back'

        elif type_.lower() == 'string':
            filename = cur.execute(f"SELECT path FROM goods WHERE title = ?", (title,)).fetchall()[0][0]

            result = asyncio.create_task(get_first_email_line(filename))
            r = await result

            data = f'login: {r[0]}\npassword: {r[1]}'

            await message.answer(data)

    else:
        await message.answer(f'Спасибо за покупку!')

    return data


async def parse_page(page_data):
    data = page_data.split('__')

    msg = f'<b>Наименование:</b> {data[0]}\n<b>Стоимость покупки:</b> {data[1]} руб.\n' \
          f'<b>Дата и время:</b> {data[2]}\n<b>Данные:</b> {data[3]}'

    return msg


async def page_manager(action, message, state):

    user_id = message.from_user.id
    data = cur.execute(f"SELECT shop_list FROM users WHERE user_id = ?", (user_id,)).fetchall()[0][0]
    data = data.split('___')[1:]

    st = await state.get_data()

    now_page = st["now_page"]
    len_page = st["next_page"]

    back = [types.KeyboardButton(text="Назад"), ]

    buttons_full = [
        types.KeyboardButton(text="<---"),
        types.KeyboardButton(text="--->"),
    ]

    buttons_next = [types.KeyboardButton(text="--->"), ]

    buttons_back = [types.KeyboardButton(text="<---"), ]

    buttons_middle = [buttons_full, back, ]
    buttons_first = [buttons_next, back, ]
    buttons_last = [buttons_back, back, ]

    if action == 0:

        if abs(now_page) < len_page:

            now_page -= 1
            await state.update_data(now_page=now_page, )

        if abs(now_page) < len_page:

            page = data[now_page]
            page = await parse_page(page)

            keyboard = types.ReplyKeyboardMarkup(
                keyboard=buttons_middle,
                resize_keyboard=True,
            )

            await message.answer(
                text=f"{page}",
                reply_markup=keyboard
            )

        elif abs(now_page) == len_page:

            page = data[now_page]
            page = await parse_page(page)

            keyboard = types.ReplyKeyboardMarkup(
                keyboard=buttons_last,
                resize_keyboard=True,
            )

            await message.answer(
                text=f"{page}",
                reply_markup=keyboard
            )
        else:
            return

    elif action == 1:

        if abs(now_page) < len_page:
            now_page += 1
            await state.update_data(now_page=now_page, )

        page = data[now_page]
        page = await parse_page(page)

        if abs(now_page) < len_page and (abs(now_page) > 1):

            keyboard = types.ReplyKeyboardMarkup(
                keyboard=buttons_middle,
                resize_keyboard=True,
            )

            await message.answer(
                text=f"{page}",
                reply_markup=keyboard
            )

        elif abs(now_page) == 1:

            keyboard = types.ReplyKeyboardMarkup(
                keyboard=buttons_first,
                resize_keyboard=True,
            )

            await message.answer(
                text=f"{page}",
                reply_markup=keyboard
            )

        elif abs(now_page) == len_page:

            now_page += 1
            page = data[now_page]
            page = await parse_page(page)

            await state.update_data(now_page=now_page, )

            keyboard = types.ReplyKeyboardMarkup(
                keyboard=buttons_middle,
                resize_keyboard=True,
            )

            await message.answer(
                text=f"{page}",
                reply_markup=keyboard
            )
        else:
            return

    await message.answer(
        text=f"{now_page}, {len_page}",
    )


# получаем баланс пользователя
async def get_balance(user_id):
    balance = cur.execute(f"SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchall()[0][0]
    return balance


# генерация соли для пополнения yoomoney
async def generate_comment(length=15):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


@dp.message(Command("demo"))
async def cmd_start(message: types.Message):

    user_id = message.from_user.id

    command = "UPDATE users SET balance = ? WHERE user_id = ?"
    balance = await get_balance(user_id)
    cur.execute(command, (balance + 100, user_id,))
    db.commit()

    await message.answer(
        text="+100 ₽")


# команда /start (работает везде и всегда)
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    # user_name = message.from_user.first_name
    user_full_name = message.from_user.full_name

    reg = cur.execute(f"SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchall()

    if not reg:
        command = "INSERT INTO users (user_id) VALUES(?)"
        cur.execute(command, (user_id,))
        db.commit()

    logging.info(f'{user_id} {user_full_name} {time.asctime()}')

    await state.clear()

    await main_menu(message)

    # await message.reply("Запуск!")
    # result_task = await asyncio.create_task(get_request_data())


# команда назад (работает везде и всегда)
@dp.message(Text("Назад"))
async def cmd_start(message: types.Message, state: FSMContext):

    await state.clear()
    await main_menu(message)


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
                                  f'<b>Цена:</b> {data[2]} руб.\n<b>Описание:</b>\n{data[3]}', reply_markup=keyboard)

        await state.update_data(choosing_goods=(data[1], data[2]))

        await state.set_state(ChoosingGoods.submit_buy)


@dp.message(OrderPage.next_page, Text('--->'))
async def next_page(message: types.Message, state: FSMContext):
    await page_manager(action=0, message=message, state=state)


@dp.message(OrderPage.next_page, Text('<---'))
async def next_page(message: types.Message, state: FSMContext):
    await page_manager(action=1, message=message, state=state)


# покупка товара
@dp.message(ChoosingGoods.submit_buy, Text("Подтвердить покупку"))
async def submit(message: Message, state: FSMContext):
    await main_menu(message)

    user_id = message.from_user.id

    last_buy = cur.execute(f"SELECT last_buy FROM users WHERE user_id = ?", (user_id, )).fetchall()[0][0]

    if float(last_buy) + 10.0 > time.time():
        await message.answer(text=f"Не так быстро!")
        return
    else:
        command = "UPDATE users SET last_buy = ? WHERE user_id = ?"
        cur.execute(command, (time.time() // 1, user_id, ))
        db.commit()

    data = await state.get_data()
    await state.clear()
    title = data["choosing_goods"][0]
    price = data["choosing_goods"][1]

    balance = await get_balance(user_id)

    if price > balance:
        await message.answer(text=f"У Вас недостаточно средств.\nПополните баланс в профиле.")

    else:

        shop_list = cur.execute(f"SELECT shop_list FROM users WHERE user_id = ?", (user_id, )).fetchall()[0][0]

        command = "UPDATE users SET balance = ? WHERE user_id = ?"
        balance = await get_balance(user_id)  # !от абуза!
        cur.execute(command, (balance - price, user_id, ))
        db.commit()

        await message.answer(text=f"Успешно!")

        type_ = cur.execute(f"SELECT type FROM goods WHERE title = ?", (title, )).fetchall()[0][0]

        result = asyncio.create_task(send_order(message=message, title=title, type_=type_))

        r = await result

        if r == 'back':
            command = "UPDATE users SET balance = ? WHERE user_id = ?"
            balance = await get_balance(user_id)  # !от абуза!
            cur.execute(command, (balance + price, user_id, ))
            db.commit()

        else:
            t = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            shop_list = f'{shop_list}___{title}__{price}__{t}__{r}'

            command = "UPDATE users SET shop_list = ? WHERE user_id = ?"
            cur.execute(command, (shop_list, user_id,))
            db.commit()


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
        add_balance_link = f'https://yoomoney.ru/quickpay/confirm.xml?receiver={wallet}&quickpay-form=button' \
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
async def goods_list(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    data = cur.execute(f"SELECT shop_list FROM users WHERE user_id = ?", (user_id, )).fetchall()[0][0]

    if data:
        data = data.split('___')[1:]
        len_data = len(data)
        await state.set_state(OrderPage.next_page)

        back = [types.KeyboardButton(text="Назад"), ]

        buttons_next = [types.KeyboardButton(text="--->"), ]
        buttons_first = [buttons_next, back, ]

        keyboard = types.ReplyKeyboardMarkup(
            keyboard=buttons_first,
            resize_keyboard=True,
        )

        page = await parse_page(page_data=data[-1])

        if len_data == 1:
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[back, ],
                resize_keyboard=True,
            )

        await message.answer(
            text=f"{page}",
            reply_markup=keyboard
        )

        await state.update_data(next_page=len_data)
        await state.update_data(now_page=-1)
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
