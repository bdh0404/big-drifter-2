import logging
import json
import os
import datetime
import re

import discord

import bot

__version__ = "0.2.6"

with open("settings.json", "r", encoding="utf-8") as f:
    options: dict = json.load(f)

client = bot.DestinyBot(**options)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("app.log", encoding="utf-8")
logger.addHandler(file_handler)
logger.addHandler(logging.StreamHandler())

discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.WARNING)


@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    # 상태 업데이트
    client_activity = discord.Activity(name="DESTINY 2", type=discord.ActivityType.watching)
    await client.change_presence(status=discord.Status.online, activity=client_activity)
    logger.info(f"Updated bot status!")
    await client.d2util.destiny.update_manifest("ko")
    logger.info("Updated Destiny 2 manifest!")


@client.event
async def on_message(message):
    if message.author.bot or not message.content.startswith("$"):
        return

    if message.content.startswith("$정보"):
        uptime = await client.get_uptime()
        msg_embed = discord.Embed(title="BIG DRIFTER 2", description="by Krepe.Z (Krepe#4364)", timestamp=datetime.datetime.utcnow(), color=0x00ac00)
        msg_embed.add_field(name="Version", value=__version__)
        msg_embed.add_field(name="PID", value=str(os.getpid()))
        msg_embed.add_field(name="Uptime", value=str(uptime), inline=False)
        msg_embed.add_field(name="Last Clan info update", value=str(client.last_tasks_run), inline=False)
        # msg_embed.add_field(name="Invite link", value="[Click here to invite this bot](https://discord.com/oauth2/authorize?client_id=618095800483840001&scope=bot)", inline=False)
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
        if client.online_command_preview:
            msg_embed = await client.get_clan_online()
            resp_msg: discord.Message = await message.channel.send(embed=msg_embed)
            msg_embed = await client.get_clan_online_detail()
            await resp_msg.edit(embed=msg_embed)
        else:
            msg_embed = await client.get_clan_online_detail()
            await message.channel.send(embed=msg_embed)

    elif message.content.startswith("$등록"):
        if message.author.guild_permissions.administrator:
            ret = await client.toggle_alert_target(message.channel.id)
            if ret == 1:
                await message.channel.send(f"<#{message.channel.id}> 채널이 알림 수신 목록에 추가되었습니다.")
            elif ret == 0:
                await message.channel.send(f"<#{message.channel.id}> 채널이 알림 수신 목록에서 제거되었습니다.")
        else:
            await message.channel.send("서버 관리자 권한이 필요합니다!")

    elif message.content.startswith("$휴가"):
        if message.author.guild_permissions.administrator:
            cmd, *desc = message.content.split("\n")
            args: list = cmd.split()
            arg1_id = None
            arg1_date = None
            arg2_date = None
            if len(args) > 2:
                arg1_id = re.search(r"^[0-9]{19}$", args[1].strip())
                arg1_id = int(arg1_id.group()) if arg1_id else 0
                arg2_date = re.search(r"([0-9]{4})?[-.]?([0-9]{1,2})[-.]([0-9]{1,2})", args[2])
                # arg1_steam = re.search(r"^[0-9]{17}$", args[1].strip() if len(args) > 1 else "")
            elif len(args) > 1:
                arg1_date = re.search(r"([0-9]{4})?[-.]?([0-9]{1,2})[-.]([0-9]{1,2})", args[1])

            if arg1_date:
                # 날짜만 입력한 경우 (자기 자신 등록)
                msg = {"content": "해당 기능은 아직 제공되지 않습니다."}
            elif arg2_date:
                # 스팀 아이디 or 번지넷 멤버십 ID / 휴가일 입력
                bungie_id: int = await client.d2util.is_member_in_clan(membership_id=arg1_id, name=args[1])
                if bungie_id:
                    y, m, d = arg2_date.groups()
                    if not y:
                        y = datetime.datetime.today().year
                    else:
                        y = int(y)
                    m, d = int(m), int(d)
                    end_date = datetime.datetime(year=y, month=m, day=d)
                    await client.register_rest(bungie_id, end_date, "\n".join(desc))
                    msg = {"content": f"{end_date.strftime('%Y-%m-%d')} 까지 휴가로 등록되었습니다."}
                else:
                    msg = {"content": "해당 유저를 찾을 수 없습니다."}
            else:
                # 제대로 입력하지 않은 경우
                msg = {"content": "양식에 따라 입력해주세요.\n> `$휴가 [닉네임|멤버십ID] (휴가종료일)`\n휴가종료일의 경우 `YYYY-MM-DD` 또는 `YYYY.MM.DD` 형식으로 입력해주세요."}
            await message.channel.send(**msg)
        else:
            await message.channel.send("서버 관리자 권한이 필요합니다!")


if __name__ == '__main__':
    client.run(options.pop("discord_token", ""))
