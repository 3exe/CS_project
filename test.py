import csv
import aiofiles
import asyncio


async def write_to_csv(user_id: int):
    async with aiofiles.open('topup.csv', mode='a', encoding='utf-8') as file:
        writer = csv.writer(file)
        await writer.writerow([user_id])
        file.close()  # добавьте эту строку


async def main():
    await write_to_csv(4565645645)

asyncio.run(main())
