import asyncio
import base64
import email
import imaplib
import logging
import os
import random
import re
import string
import aiofiles
import aiohttp

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


# получаем первую строку из текстовика
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


async def check_proxy(proxy):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get('https://ruvds.com', proxy=f'https://{proxy}', timeout=500) as response:
                if response.status == 200:
                    return True
                else:
                    print(response.status)
                    return False
        except Exception as e:
            print(e)
            return False


flows = 0  # занятые потоки
max_flows = config.max_flows  # максимум потоков


async def get_request_data(message):

    global flows

    if flows >= max_flows:
        return False, 'Все потоки заняты.. повторите позднее'

    else:

        result_task = asyncio.create_task(get_first_email_line('proxy.txt'))
        r = await result_task
        proxy = f'{r[0]}:{r[1]}'
        print(proxy)

        result_task = asyncio.create_task(check_proxy(proxy))
        r = await result_task

        if not r:
            return False, 'Прокси не прошел проверку'

        flows += 1
        await message.answer(f'Запуск скрипта.. сейчас потоков занято: {flows}/{max_flows}')

        done = 0

        future = asyncio.Future()
        browser = await launch({
            'args': [
                f'--proxy-server=https://{proxy}',
                '--no-sandbox'
            ],
            'ignoreHTTPSErrors': True
        })

        page = await browser.newPage()
        await page.setViewport({'width': random.randint(1024, 1920), 'height': random.randint(768, 1080)})  # ##########
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
            result = "Возникли проблемы на этапе решения капчи. попробуйте снова..."
            return result

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
            await browser.close()
            latest_email = await get_latest_email(login, eml_password)
            if latest_email:
                unicode_string = latest_email.decode('utf-8')
                match = re.search(r'Ваш пароль:</span> <strong>\s*(.*?)\s*</', unicode_string)  # \s*(.*?)\s*

                if match:
                    vds_password = match.group(1)
                    print(vds_password)

                    new_password = await change_pass(login, vds_password, final_id, eml_password)

                    print(new_password)

                    result = f'{login}:{vds_password}'

                    done = 1

                    # print(await add_data(eml_password, final_id, login))

            else:
                result = "Возникли проблемы на этапе получения письма. попробуйте снова..."

        except TimeoutError:
            # Если элемент не найден, выводим сообщение об ошибке
            print('Element not found!')

            result = "Возникли проблемы на этапе регистрации аккаунта. попробуйте снова..."

        flows -= 1
        return done, result
