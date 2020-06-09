import logging
import discord
import json

import bot

__version__ = "0.1.4"

with open("settings.json", "r", encoding="utf-8") as f:
    options: dict = json.load(f)

client = bot.DestinyBot(**options)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("app.log", encoding="utf-8")
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())


@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    # 상태 업데이트
    client_activity = discord.Activity(name="DESTINY 2", type=discord.ActivityType.watching)
    logger.info(f"Updated bot status!")
    await client.change_presence(status=discord.Status.online, activity=client_activity)


@client.event
async def on_message(message):
    if message.author == client.user and not message.content.startswith("$"):
        return

    if message.content.startswith("$정보"):
        await message.channel.send(f"**BIG DRIFTER 2**\nv{__version__}")

    elif message.content.startswith("$미접"):
        args: list = message.content.split()
        if len(args) < 2:
            msg = await client.get_long_offline()
        elif args[1].isdigit():
            msg = await client.get_long_offline(int(args[1]))
        else:
            msg = "올바른 미접 커트라인(일 단위)을 입력해주세요."
        await message.channel.send(msg)

    elif message.content.startswith("$등록"):
        pass

    elif message.content.startswith("$업타임"):
        uptime = await client.get_uptime()
        await message.channel.send(f"작동시간: {uptime}")


if __name__ == '__main__':
    client.run(options.pop("discord_token", ""))
