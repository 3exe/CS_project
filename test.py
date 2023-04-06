import aiohttp
import asyncio
import aiofiles


async def check_proxy(proxy):
    proxy_url = 'https://194.34.248.143:1050'
    proxy_auth = aiohttp.BasicAuth('X0j7jo', 'WvUku9LwQx')
    connector = aiohttp.TCPConnector(ssl=True)
    session = aiohttp.ClientSession(connector=connector)

    async with session.get(proxy_url, auth=proxy_auth) as response:
        async with session.get('https://ruvds.com') as response:
            try:
                if response.status == 200:
                    print('done')
                    return True
                else:
                    print(response.status)
                    return False

            except Exception as e:
                print(e)
                return False


async def get_first_email_line(filename):
    # async with aiofiles.open(filename, 'r+') as f:
    #     lines = await f.readlines()
    #     first_line = lines[0]
    #     await f.seek(0)
    #     await f.writelines(lines[1:])
    #     await f.truncate()
    # return first_line.strip().split(':')
    return 0, 0


async def main():
    result_task = asyncio.create_task(get_first_email_line('proxy.txt'))
    r = await result_task
    proxy = f'{r[0]}:{r[1]}'
    print(proxy)

    result_task = asyncio.create_task(check_proxy(proxy))
    r = await result_task

    if not r:
        return None, 'Прокси не прошел проверку'
    else:
        return 1, None

res = 0

while not res:

    res = asyncio.run(main())[0]
    print(res)
