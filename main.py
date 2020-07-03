import logging
import json
import os
import datetime

import discord

import bot

__version__ = "0.2.0"

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
    if message.author.bot or not message.content.startswith("$"):
        return

    if message.content.startswith("$정보"):
        uptime = await client.get_uptime()
        msg_embed = discord.Embed(description="by Krepe.Z (Krepe#4364)", timestamp=datetime.datetime.utcnow(), color=0x00ac00)
        msg_embed.add_field(name="Version", value=__version__)
        msg_embed.add_field(name="PID", value=str(os.getpid()))
        msg_embed.add_field(name="Uptime", value=str(uptime), inline=False)
        msg_embed.add_field(name="Last Clan info update", value=str(client.last_tasks_run), inline=False)
        msg_embed.add_field(name="Invite link", value="[Click here to invite this bot](https://discord.com/oauth2/authorize?client_id=618095800483840001&scope=bot)", inline=False)
        await message.channel.send(embed=msg_embed)

    elif message.content.startswith("$미접"):
        args: list = message.content.split()
        if len(args) < 2:
            msg_embed = await client.get_long_offline()
            msg = {"embed": msg_embed}
        elif args[1].isdigit():
            msg_embed = await client.get_long_offline(int(args[1]))
            msg = {"embed": msg_embed}
        else:
            msg = {"content": "올바른 미접 커트라인(일 단위)을 입력해주세요."}
        await message.channel.send(**msg)

    elif message.content.startswith("$온라인"):
        msg_embed = await client.get_clan_online()
        await message.channel.send(embed=msg_embed)

    elif message.content.startswith("$등록"):
        if message.author.guild_permissions.administrator:
            ret = await client.toggle_alert_target(message.channel.id)
            if ret == 1:
                await message.channel.send(f"{message.channel.name} 채널이 알림 수신 목록에 추가되었습니다.")
            elif ret == 0:
                await message.channel.send(f"{message.channel.name} 채널이 알림 수신 목록에서 제거되었습니다.")
        else:
            await message.channel.send("서버 관리자 권한이 필요합니다!")


if __name__ == '__main__':
    client.run(options.pop("discord_token", ""))
