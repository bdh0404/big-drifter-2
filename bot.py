import asyncio
import datetime as dt
import json
import logging
import re
import time
import os
from typing import List, Optional

import discord
from discord.ext import tasks

import destiny2


logger = logging.getLogger("bot")


def escape_markdown(s: str) -> str:
    return re.sub(r"([-_~`*])", "\\\\\\1", s)


def bnet_user_format(d: dict, bold=True, skip_bnet_name=True) -> str:
    if bold:
        name = f"**{escape_markdown(d['destinyUserInfo']['bungieGlobalDisplayName'])}**#{d['destinyUserInfo']['bungieGlobalDisplayNameCode']:04d}" if d['destinyUserInfo'].get("bungieGlobalDisplayName") else f"**{d['destinyUserInfo']['LastSeenDisplayName']}**"
    else:
        name = f"{escape_markdown(d['destinyUserInfo']['bungieGlobalDisplayName'])}#{d['destinyUserInfo']['bungieGlobalDisplayNameCode']:04d}" if d['destinyUserInfo'].get("bungieGlobalDisplayName") else f"{d['destinyUserInfo']['LastSeenDisplayName']}"
    url = f"https://www.bungie.net/7/ko/User/Profile/{d['bungieNetUserInfo']['membershipType']}/{d['bungieNetUserInfo']['membershipId']}" if d.get("bungieNetUserInfo") else f"https://www.bungie.net/7/ko/User/Profile/{d['destinyUserInfo']['membershipType']}/{d['destinyUserInfo']['membershipId']}"

    if not d.get('bungieNetUserInfo', {}).get('displayName', ''):
        bnet_name = ""
    elif skip_bnet_name and d['destinyUserInfo'].get("bungieGlobalDisplayName"):
        bnet_name = f" ({escape_markdown(d['bungieNetUserInfo']['displayName'])})" if d["destinyUserInfo"]["bungieGlobalDisplayName"] != d["bungieNetUserInfo"]["displayName"] else ""
    elif skip_bnet_name:
        bnet_name = f" ({escape_markdown(d['bungieNetUserInfo']['displayName'])})" if d['destinyUserInfo']['LastSeenDisplayName'] != d["bungieNetUserInfo"]["displayName"] else ""
    else:
        bnet_name = f" ({escape_markdown(d['bungieNetUserInfo']['displayName'])})"
    result = f"[{name}]({url}){bnet_name}"
    return result


def bnet_user_format2(bungie_name: str, membership_id: int, membership_type: int = -1, bold=True, add_url=True) -> str:
    name, code = bungie_name.rsplit("#", 1)
    code = int(code)
    md_name = f"**{escape_markdown(name)}**#{code:04d}" if bold else f"{name}#{code:04d}"
    url = f"https://www.bungie.net/7/ko/User/Profile/{membership_type}/{membership_id}"
    return f"[{md_name}]({url})" if add_url else md_name


class DestinyBot(discord.Client):
    def __init__(self, *, loop=None, intents, **options):
        super(DestinyBot, self).__init__(loop=loop, intents=intents, **options)
        self._api_key = options.pop("bungie_api_key")
        self._group_id = options.pop("group_id")
        self._dir_data = "data"
        self._path_members_list = os.path.join(self._dir_data, "members.json")
        self._path_push_list = os.path.join(self._dir_data, "push_list.json")
        self._path_rest_list = os.path.join(self._dir_data, "rest_list.json")
        self._path_block_list = os.path.join(self._dir_data, "block_list.json")

        self.st = dt.datetime.now()
        self.offline_cut = options.pop("offline_cut", 14)
        self.online_command_preview = options.pop("online_command_preview", False)
        self.last_tasks_run = None
        self._cache = {}
        self.rest = {}
        self.block = {}

        if not os.path.exists(self._dir_data):
            os.makedirs(self._dir_data)
        if not os.path.exists(self._path_push_list):
            with open(self._path_push_list, "w", encoding="utf-8") as f:
                f.write("{}")
        if not os.path.exists(self._path_rest_list):
            with open(self._path_rest_list, "w", encoding="utf-8") as f:
                f.write("{}")
        if not os.path.exists(self._path_block_list):
            with open(self._path_block_list, "w", encoding="utf-8") as f:
                f.write("{}")

        with open(self._path_push_list, "r", encoding="utf-8") as f:
            self.alert_target: list = json.load(f).pop("alert_target", [])
        with open(self._path_rest_list, "r", encoding="utf-8") as f:
            self.rest = json.load(f)
            # sorting
            self.rest = dict(sorted(self.rest.items(), key=lambda x: x[1]["end_time"]))
        with open(self._path_block_list, "r", encoding="utf-8") as f:
            self.block = json.load(f)

        if not self.alert_target:
            logger.warning("Empty alert target list!!")

    def get_cache(self, key, t=10):
        if key in self._cache and self._cache[key][0] > time.time() - t:
            return self._cache[key][1]
        else:
            return None

    def set_cache(self, key, value):
        self._cache[key] = (time.time(), value)

    async def reload_alert_target(self):
        with open(self._path_push_list, "r", encoding="utf-8") as f:
            self.alert_target = json.load(f).pop("alert_target", [])
        return len(self.alert_target)

    async def update_alert_target(self):
        with open(self._path_push_list, "r", encoding="utf-8") as f:
            push_list = json.load(f)
        push_list["alert_target"] = self.alert_target
        with open(self._path_push_list, "w", encoding="utf-8") as f:
            json.dump(push_list, f, indent=2)

    async def toggle_alert_target(self, channel_id: int) -> bool:
        if channel_id in self.alert_target:
            self.alert_target.remove(channel_id)
            ret = False
        else:
            self.alert_target.append(channel_id)
            ret = True
        await self.update_alert_target()
        return ret

    async def get_uptime(self) -> str:
        return str(dt.datetime.now() - self.st)

    async def get_clan_online(self) -> discord.Embed:
        online = list(await self.d2util.online_members())
        self.set_cache("online", online)
        data = [{'dp_name': n['destinyUserInfo']['LastSeenDisplayName'],
                 'membership_id': n['destinyUserInfo']['membershipId'],
                 'bungie_name': n.get('bungieNetUserInfo', {}).get('displayName', "")}
                for n in online]

        msg_embed = discord.Embed(title="접속중인 클랜원 목록", timestamp=dt.datetime.now(), color=0x00ac00)
        msg_embed.add_field(
            name=f"온라인 ({len(data)})",
            value="\n".join(escape_markdown(f"{n['dp_name']}") for n in data),
            inline=False
        )
        return msg_embed

    async def get_clan_online_detail(self):
        online = self.get_cache("online")
        if online is None:
            online = await self.d2util.online_members()
        data = [{'dp_name': n['destinyUserInfo']['LastSeenDisplayName'],
                 'membership_type': n['destinyUserInfo']['membershipType'],
                 'membership_id': n['destinyUserInfo']['membershipId']}
                for n in online]

        res = await asyncio.gather(*[self.d2util.user_activity(member["membership_type"], member["membership_id"]) for member in data])
        for i, act in enumerate(res):
            data[i]["activity"] = act

        data_by_type = {}
        for n in data:
            if data_by_type.get(n["activity"][0]):
                data_by_type[n["activity"][0]].append(n)
            else:
                data_by_type[n["activity"][0]] = [n]

        msg_embed = discord.Embed(title=f"접속중인 클랜원 목록 ({len(data)})", timestamp=dt.datetime.now(), color=0x00ac00)
        for act_type, members in data_by_type.items():
            msg_embed.add_field(
                name=f"{act_type} ({len(members)})",
                value="\n".join(
                    f"{escape_markdown(n['dp_name'])}{' - ' + ': '.join(n['activity'][1:]) if len(n['activity']) > 1 else ''}"
                    for n in members
                ),
                inline=False
            )
        return msg_embed

    async def get_long_offline(self, offline_cut=0) -> discord.Embed:
        cut = offline_cut if offline_cut else self.offline_cut
        # target: 유저 정보 담긴 dict 객체들의 list
        target = await self.d2util.members_offline_time(cut)
        await self.update_rest()
        data = [{'name': bnet_user_format(n),
                 'membership_id': n['destinyUserInfo']['membershipId'],
                 'last_online': dt.timedelta(seconds=int(dt.datetime.now().timestamp()) - int(n['lastOnlineStatusChange'])),
                 'is_in_rest': n['destinyUserInfo']['membershipId'] in self.rest}
                for n in target]
        msg_embed = discord.Embed(title=f"{cut}일 이상 미접속자 목록", timestamp=dt.datetime.now(), color=0x00ac00)
        msg_embed.description = "\n".join((f"~~{n['name']}~~" if n['is_in_rest'] else n["name"]) + f": `{n['last_online']}`" for n in data)
        return msg_embed

    async def msg_members_diff(self, joined: list, left: list) -> List[discord.Embed]:
        list_joined = [bnet_user_format(n) for n in joined]
        list_left = [bnet_user_format(n) for n in left]
        clan_m_cnt = len(self.d2util.members_data_cache)
        clan_m_cnt_old = clan_m_cnt - len(joined) + len(left)

        msg_joined = []
        msg_left = []
        for m in list_joined:
            if msg_joined and len(msg_joined[-1]) + len(m) < 1024:
                msg_joined[-1] += m + "\n"
            else:
                msg_joined.append(m + "\n")
        for m in list_left:
            if msg_left and len(msg_left[-1]) + len(m) < 1024:
                msg_left[-1] += m + "\n"
            else:
                msg_left.append(m + "\n")

        msg_embed = discord.Embed(
            title="클랜원 목록 변동 안내",
            description=f"{clan_m_cnt_old}명 -> {clan_m_cnt}명 ({len(joined) - len(left):+})\n<t:{int(time.time())}>",
            timestamp=dt.datetime.now(),
            color=0x00ac00
        )
        embeds = [msg_embed]
        field_cnt = 0
        while True:
            if field_cnt >= 5:
                embeds.append(discord.Embed(description="클랜원 목록 변동 안내 (+)", timestamp=dt.datetime.now(), color=0x00ac00))
                field_cnt = 0

            if msg_joined:
                embeds[-1].add_field(name=":blue_circle: Joined", value=msg_joined.pop(0), inline=False)
                field_cnt += 1
            elif msg_left:
                embeds[-1].add_field(name=":red_circle: Left", value=msg_left.pop(0), inline=False)
                field_cnt += 1
            else:
                break
        return embeds

    async def register_rest(self, group_member: dict, end_time: dt.datetime, msg_url: str, description: str):
        membership_id = group_member["destinyUserInfo"]["membershipId"]
        if len(description) > 500:
            description = description[:500]
        self.rest[membership_id] = {
            "bungie_name": destiny2.get_bungie_name(group_member),
            "display_name": group_member["destinyUserInfo"]["LastSeenDisplayName"],
            "end_time": end_time.strftime("%Y-%m-%d"),
            "msg_url": msg_url,
            "description": description
        }
        self.rest = dict(sorted(self.rest.items(), key=lambda x: x[1]["end_time"]))
        with open(self._path_rest_list, "w", encoding="utf-8") as f:
            json.dump(self.rest, f, ensure_ascii=False, indent=2)

    async def deregister_rest(self, membership_id: int):
        self.rest.pop(membership_id, None)
        with open(self._path_rest_list, "w", encoding="utf-8") as f:
            json.dump(self.rest, f, ensure_ascii=False, indent=2)

    async def update_rest(self):
        # 휴가 목록 갱신: 날짜 만료된 클랜원, 클랜을 나간 클랜원 제거
        # 추가로 닉네임 정보 없으면 넣기
        today = dt.datetime.today()
        members = {n["destinyUserInfo"]["membershipId"]: n for n in self.d2util.members_data_cache}
        rest_new = {}
        for k, v in self.rest.items():
            if dt.datetime.strptime(v["end_time"], "%Y-%m-%d") < today or k not in members:
                continue
            if not v.get("bungie_name"):
                v["bungie_name"] = destiny2.get_bungie_name(members[k]) if destiny2.get_bungie_name(members[k]) else ""
            if not v.get("display_name"):
                v["display_name"] = members[k]["destinyUserInfo"]["LastSeenDisplayName"]
            rest_new[k] = v

        self.rest = {k: v for k, v in self.rest.items() if dt.datetime.strptime(v["end_time"], "%Y-%m-%d") > today and k in members.keys()}
        with open(self._path_rest_list, "w", encoding="utf-8") as f:
            json.dump(self.rest, f, ensure_ascii=False, indent=2)

    async def msg_rest_list(self):
        await self.update_rest()
        msg_embed = discord.Embed(title="휴가중인 클랜원 목록 조회", timestamp=dt.datetime.now(), color=0x00ac00)
        if self.rest:
            msg_embed.description = "\n".join(
                f"{bnet_user_format(self.d2util.find_member_from_cache(bungie_name=v['bungie_name'], membership_id=k))} `~{v['end_time']}`\n> "
                + v["description"].replace("\n", "\n> ")
                + (f" [(링크)]({v['msg_url']})" if v.get("msg_url") else "")
                for k, v in self.rest.items()
            )
        return msg_embed

    async def register_block(self, bungie_name: str = "", steam_id: str = "", msg_url: str = "", description: str = "") -> bool:
        if bungie_name:
            user_info = await self.d2util.search_player(bungie_name=bungie_name)
        elif steam_id:
            user_info = await self.d2util.get_player_from_steam_id(steam_id=steam_id)
        else:
            return False
        if not user_info:
            return False
        mem_id = user_info["membershipId"]
        self.block[mem_id] = {
            "bungie_name": "{bungieGlobalDisplayName}#{bungieGlobalDisplayNameCode:04d}".format(**user_info),
            "membership_id": mem_id,
            "membership_type": user_info["membershipType"],
            "time": int(time.time()),
            "msg_url": msg_url,
            "description": description
        }
        with open(self._path_block_list, "w", encoding="utf-8") as f:
            json.dump(self.block, f, ensure_ascii=False, indent=2)
        return True

    async def deregister_block(self, bungie_name: str = "", steam_id: str = "") -> bool:
        if bungie_name:
            user_info = await self.d2util.search_player(bungie_name=bungie_name)
        elif steam_id:
            user_info = await self.d2util.get_player_from_steam_id(steam_id=steam_id)
        else:
            return False
        if not user_info:
            return False
        self.block.pop(user_info["membershipId"], None)
        with open(self._path_block_list, "w", encoding="utf-8") as f:
            json.dump(self.block, f, ensure_ascii=False, indent=2)
        return True

    async def msg_block_list(self, page=1):
        block_cnt = len(self.block)
        max_page = (block_cnt - 1) // 10 + 1
        if page >= 0:
            current_page = page if 0 < page <= max_page else 1
        else:
            current_page = max_page + 1 + page
            current_page = 1 if current_page <= 0 else current_page
        block_list = [n for i, n in enumerate(self.block.values()) if (i // 10 + 1) == current_page]
        msg_embed = discord.Embed(title=f"차단된 유저 목록 조회 ({current_page}/{max_page})", timestamp=dt.datetime.now(), color=0x00ac00)
        if not block_list:
            msg_embed.description = "차단된 유저가 없습니다."
        for v in block_list:
            msg_embed.add_field(
                name=v['bungie_name'],
                value=f"차단 일시: <t:{v['time']}>\n[번지넷 프로필](https://www.bungie.net/7/ko/User/Profile/{v['membership_type']}/{v['membership_id']})" +
                      (f" / [참조 링크]({v['msg_url']})" if v.get("msg_url") else "") +
                      f"\n```\n{v['description']}\n```",
                inline=False
            )
        return msg_embed

    async def msg_block_list_verify(self, joined_list: list) -> Optional[discord.Embed]:
        blocked = [self.block[n["destinyUserInfo"]["membershipId"]] for n in joined_list if n["destinyUserInfo"]["membershipId"] in self.block]
        if not blocked:
            return None
        else:
            msg_embed = discord.Embed(title=f":no_entry_sign: 차단된 유저의 클랜 가입 확인!!", timestamp=dt.datetime.now(), color=0x00ac00)
            for v in blocked:
                msg_embed.add_field(
                    name=v['bungie_name'],
                    value=f"차단 일시: <t:{v['time']}>\n[번지넷 프로필](https://www.bungie.net/7/ko/User/Profile/{v['membership_type']}/{v['membership_id']})" +
                          (f" / [참조 링크]({v['msg_url']})" if v.get("msg_url") else "") +
                          f"\n```\n{v['description']}\n```",
                    inline=False
                )
            return msg_embed

    async def alert(self):
        logger.debug("Alert Task start!")
        alert_target = [self.get_channel(n) for n in self.alert_target]
        # 클랜원 변화 목록 파싱
        try:
            joined, left = await self.d2util.member_diff()
        except Exception as e:
            logger.error(f"Error occurred while getting member diff: {e}")
            return
        # 단순 출력
        if joined or left:
            logger.info(f"Alert detected: {len(joined)}, {len(left)}")
            msg_embed = await self.msg_members_diff(joined, left)
            msg_blocked = await self.msg_block_list_verify(joined)
            if msg_blocked:
                msg_embed.append(msg_blocked)

            # 대충 메시지 보내는 부분
            for target in alert_target:
                if target is not None:
                    for msg in msg_embed:
                        await target.send(embed=msg)
        else:
            pass
        logger.debug("Alert Task end")
        return

    async def setup_hook(self) -> None:
        self.d2util = destiny2.ClanUtil(self._api_key, self._group_id, members_data_path=self._path_members_list)
        await self.d2util.destiny.update_manifest("ko")
        logger.info(f"Loop task start")
        self.loop_tasks.start()

    @tasks.loop(seconds=3600)
    async def loop_tasks(self):
        # 로딩될때까지 대기
        if self.is_closed():
            logger.warning(f"Discord bot client closed!!")
            return
        logger.debug("Creating tasks")
        await self.alert()
        logger.debug("Creating tasks end. sleep 60 secs...")
        # 봇에서 가동중임을 확인하기 위해 최근 가동시간을 저장
        self.last_tasks_run = time.time()
    
    @loop_tasks.before_loop
    async def before_task(self):
        await self.wait_until_ready()

    def run(self, *args, **kwargs):
        # super 실행
        super(DestinyBot, self).run(*args, **kwargs)
