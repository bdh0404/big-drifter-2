import logging
import discord
import json

import bot

with open("settings.json", "r", encoding="utf-8") as f:
    options: dict = json.load(f)

client = bot.DestinyBot(bungie_api_key=options.pop("bungie_api_key"))


@client.event
async def on_ready():
    # TODO logging 모듈로 변경
    print(f"Logged in as {client.user}")
    # 상태 업데이트
    client_activity = discord.Activity(name="DESTINY 2", type=discord.ActivityType.watching)
    await client.change_presence(status=discord.Status.online, activity=client_activity)


@client.event
async def on_message(message):
    if message.content.startswith("$정보"):
        await message.channel.send(f"BIG DRIFTER 2")
    elif message.content.startswith("$미접"):
        await message.channel.send("대충 미접 기간 누군지 알려주는 내용.")
    elif message.content.startswith("$등록"):
        # 등록 알림, 미접신고
        pass


if __name__ == '__main__':
    client.run(options.pop("discord_token", ""))
