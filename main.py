import logging
import json
import os
import datetime
import re
from distutils.util import strtobool

import discord
import dotenv

import bot

__version__ = "0.5.0"

dotenv.load_dotenv()
options = {
    "bungie_api_key": os.getenv("BUNGIE_API_KEY", ""),
    "discord_token": os.getenv("DISCORD_TOKEN", ""),
    "group_id": int(os.getenv("GROUP_ID", 0)),
    "offline_cut": int(os.getenv("OFFLINE_CUT", 14)),
    "online_command_preview": strtobool(os.getenv("ONLINE_COMMAND_PREVIEW", "false"))
}

client = bot.DestinyBot(**options)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
file_handler = logging.FileHandler("data/app.log", encoding="utf-8")
file_handler.setFormatter(formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.WARNING)


@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    # 상태 업데이트
    client_activity_init = discord.Activity(name="Initializing", type=discord.ActivityType.custom)
    await client.change_presence(status=discord.Status.online, activity=client_activity_init)
    logger.info("Start initializing...")
    client_activity = discord.Activity(name="DESTINY 2", type=discord.ActivityType.watching)
    await client.d2util.destiny.update_manifest("ko")
    logger.info("Updated Destiny 2 manifest!")
    await client.change_presence(status=discord.Status.online, activity=client_activity)
    logger.info(f"Updated bot status!")


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
        msg_embed.add_field(name="Last Clan info update", value=f"<t:{int(client.last_tasks_run)}:T>", inline=False)
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
            cmd = message.content.strip()
            pattern = re.compile(r"[$]휴가 (등록|조회|해제)?\s?((.+#\d{3,4})|(\d{19}))?\s?(\d{4}-[01]?\d-[ 0123]\d)?\s?(https?://[/.\w\d]+)?\s?(.+)?")
            regex_result = pattern.match(cmd)

            if regex_result:
                arg_mode = regex_result.group(1) if regex_result.group(1) else "등록"
                arg_id = regex_result.group(2)
                arg_name = regex_result.group(3)
                arg_mem_id = regex_result.group(4)
                arg_date = regex_result.group(5)
                arg_url = regex_result.group(6)
                arg_desc = regex_result.group(7)

                if arg_url is None:
                    arg_url = ""
                if arg_desc is None:
                    arg_desc = ""

                if arg_mode == "등록":
                    # 클랜에 해당 유저가 있는지 검색
                    member_info: dict = await client.d2util.is_member_in_clan(bungie_name=arg_name, membership_id=arg_mem_id)
                    if not (arg_id and arg_date):
                        msg = {"content": "양식에 따라 입력해주세요.\n> `$휴가 [등록|조회|해제] (번지 이름|멤버쉽 ID) (휴가종료일) [URL] [설명]`\n휴가종료일의 경우 `YYYY-MM-DD` 또는 `YYYY.MM.DD` 형식으로 입력해주세요."}
                    elif member_info:
                        y, m, d = map(int, re.match(r"(\d{4})-(\d{2})-(\d{2})", arg_date).groups())
                        end_date = datetime.datetime(year=y, month=m, day=d)
                        await client.register_rest(member_info, end_date, arg_url, arg_desc)
                        msg = {"content": f"{end_date.strftime('%Y-%m-%d')} 까지 휴가로 등록되었습니다."}
                    else:
                        msg = {"content": "해당 유저를 찾을 수 없습니다."}
                elif arg_mode == "해제":
                    msg = {"content": "지원 예정 기능"}
                elif arg_mode == "조회":
                    msg_embed = await client.msg_rest_list()
                    msg = {"embed": msg_embed}
                else:
                    msg = {"content": "알 수 없는 모드 이름"}
            else:
                # 제대로 입력하지 않은 경우
                msg = {"content": "양식에 따라 입력해주세요.\n> `$휴가 [등록|조회|해제] (번지 이름|멤버쉽 ID) (휴가종료일) [URL] [설명]`\n휴가종료일의 경우 `YYYY-MM-DD` 또는 `YYYY.MM.DD` 형식으로 입력해주세요."}
            await message.channel.send(**msg)
        else:
            await message.channel.send("서버 관리자 권한이 필요합니다!")

    elif message.content.startswith("$차단"):
        if not message.author.guild_permissions.administrator:
            await message.channel.send("서버 관리자 권한이 필요합니다!")
            return

        cmd = message.content.strip()
        pattern = re.compile(r"[$]차단 (등록|조회|해제)?\s?((.+#\d{3,4})|(\d{17})|([-]?\d))?\s?(https?://[\w\d.@?^=%&/~+#]+)?\s?([\s\S]+)?", re.MULTILINE)
        regex_result = pattern.match(cmd)
        if not regex_result:
            await message.channel.send("양식에 따라 입력해주세요.\n> `$차단 [등록|조회|해제] (번지 이름|SteamID64) [URL] [설명]`")
            return

        arg_mode = regex_result.group(1) if regex_result.group(1) else "등록"
        arg_name = regex_result.group(3)
        arg_steam_id = regex_result.group(4)
        arg_page = regex_result.group(5)
        arg_url = regex_result.group(6)
        arg_desc = regex_result.group(7)

        if arg_url is None:
            arg_url = ""
        if arg_desc is None:
            arg_desc = "(사유 없음)"
        else:
            arg_desc = arg_desc.strip()

        if arg_mode == "등록":
            if not (arg_name or arg_steam_id):
                await message.channel.send("양식에 따라 입력해주세요.\n> `$차단 등록 (번지 이름|SteamID64) [URL] [설명]`")
                return
            ret = await client.register_block(arg_name, arg_steam_id, arg_url, arg_desc)
            msg = {"content": f"`{arg_name if arg_name else arg_steam_id}` 차단 등록 성공"} if ret else {"content": f"`{arg_name if arg_name else arg_steam_id}` 차단 등록 실패"}
        elif arg_mode == "해제":
            if not arg_name:
                await message.channel.send("양식에 따라 입력해주세요.\n> `$차단 등록 (번지 이름|SteamID64) [URL] [설명]`")
                return
            ret = await client.deregister_block(arg_name, arg_steam_id)
            msg = {"content": f"`{arg_name if arg_name else arg_steam_id}` 차단 해제 성공"} if ret else {"content": f"`{arg_name if arg_name else arg_steam_id}` 차단 해제 실패"}
        elif arg_mode == "조회":
            page = int(arg_page) if arg_page else 1
            msg_embed = await client.msg_block_list(page)
            msg = {"embed": msg_embed}
        else:
            msg = {"content": "양식에 따라 입력해주세요.\n> `$차단 등록 (번지 이름|SteamID64) [URL] [설명]`"}
        await message.channel.send(**msg)


if __name__ == '__main__':
    client.run(options.pop("discord_token", ""))
