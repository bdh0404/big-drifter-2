import asyncio
import datetime as dt
import json
import logging
import re
import time

import discord

import destiny2


logger = logging.getLogger("bot")


def escape_markdown(s: str) -> str:
    return re.sub(r"([-_~`*])", "\\\\\\1", s)


class DestinyBot(discord.Client):
    def __init__(self, *, loop=None, **options):
        super(DestinyBot, self).__init__(loop=loop, **options)
        self.d2util = destiny2.ClanUtil(options.pop("bungie_api_key"), options.pop("group_id"), loop=self.loop)
        self.st = dt.datetime.now()
        self.offline_cut = options.pop("offline_cut", 14)
        self.last_tasks_run = None
        self._cache = {}
        with open("push_list.json", "r", encoding="utf-8") as f:
            self.alert_target: list = json.load(f).pop("alert_target", [])

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
        with open("push_list.json", "r", encoding="utf-8") as f:
            self.alert_target = json.load(f).pop("alert_target", [])
        return len(self.alert_target)

    async def update_alert_target(self):
        with open("push_list.json", "r", encoding="utf-8") as f:
            push_list = json.load(f)
        push_list["alert_target"] = self.alert_target
        with open("push_list.json", "w", encoding="utf-8") as f:
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

        msg_embed = discord.Embed(title="접속중인 클랜원 목록", timestamp=dt.datetime.utcnow(), color=0x00ac00)
        msg_embed.add_field(name=f"온라인 ({len(data)})", value="\n".join(escape_markdown(f"{n['dp_name']}") for n in data), inline=False)
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

        msg_embed = discord.Embed(title=f"접속중인 클랜원 목록 ({len(data)})", timestamp=dt.datetime.utcnow(), color=0x00ac00)
        for act_type, members in data_by_type.items():
            msg_embed.add_field(name=f"{act_type} ({len(members)})", value="\n".join(f"{escape_markdown(n['dp_name'])}{' - ' + ': '.join(n['activity'][1:]) if len(n['activity']) > 1 else ''}" for n in members), inline=False)
        return msg_embed

    async def get_long_offline(self, offline_cut=0) -> discord.Embed:
        cut = offline_cut if offline_cut else self.offline_cut
        # target: 유저 정보 담긴 dict 객체들의 list
        target = await self.d2util.members_offline_time(cut)
        data = [{'dp_name': n['destinyUserInfo']['LastSeenDisplayName'],
                 'membership_id': n['destinyUserInfo']['membershipId'],
                 'bungie_name': n.get('bungieNetUserInfo', {}).get('displayName', ""),
                 'last_online': dt.timedelta(seconds=int(dt.datetime.utcnow().timestamp()) - int(n['lastOnlineStatusChange']))}
                for n in target]
        msg_embed = discord.Embed(title=f"{cut}일 이상 미접속자 목록", timestamp=dt.datetime.utcnow(), color=0x00ac00)
        msg_embed.description = "\n".join(f"**{n['dp_name']}** ({n['bungie_name']}): `{n['last_online']}`" for n in data)
        return msg_embed

    async def msg_members_diff(self, joined: list, leaved: list) -> discord.Embed:
        msg_joined = [f"[{n['destinyUserInfo']['LastSeenDisplayName']}](https://destinytracker.com/destiny-2/profile/steam/{n['destinyUserInfo']['membershipId']}/overview) ({n.get('bungieNetUserInfo', {}).get('displayName', '')})" for n in joined]
        msg_leaved = [f"[{n['destinyUserInfo']['LastSeenDisplayName']}](https://destinytracker.com/destiny-2/profile/steam/{n['destinyUserInfo']['membershipId']}/overview) ({n.get('bungieNetUserInfo', {}).get('displayName', '')})" for n in leaved]
        clan_m_cnt = len(self.d2util.members_data_cache)
        clan_m_cnt_old = clan_m_cnt - len(joined) + len(leaved)

        msg_embed = discord.Embed(title="클랜원 목록 변동 안내", description=f"{clan_m_cnt_old}명 -> {clan_m_cnt}명 ({len(joined) - len(leaved):+})", timestamp=dt.datetime.utcnow(), color=0x00ac00)
        if joined:
            msg_embed.add_field(name=":blue_circle: Joined", value="\n".join(msg_joined), inline=False)
        if leaved:
            msg_embed.add_field(name=":red_circle: Leaved", value="\n".join(msg_leaved), inline=False)
        return msg_embed

    async def alert(self):
        logger.debug("Alert Task start!")
        alert_target = [self.get_channel(id=n) for n in self.alert_target]
        # 클랜원 변화 목록 파싱
        joined, leaved = await self.d2util.member_diff()
        # 단순 출력
        if joined or leaved:
            logger.info(f"{dt.datetime.now()} Alert detected: {len(joined)}, {len(leaved)}")
            msg_embed = await self.msg_members_diff(joined, leaved)

            # TODO joined list 의 member 에 대한 검증 필요
            # Verify code here

            # 대충 메시지 보내는 부분
            for target in alert_target:
                if target is not None:
                    await target.send(embed=msg_embed)
        else:
            pass
        logger.debug("Alert Task end")
        return

    async def tasks(self):
        # 로딩될때까지 대기
        await self.wait_until_ready()
        logger.info(f"{dt.datetime.now()} loop task start")
        while True:
            if self.is_closed():
                logger.warning(f"{dt.datetime.now()} client closed!!")
                await asyncio.sleep(60)
                continue
            logger.debug("Creating tasks")
            self.loop.create_task(self.alert())
            logger.debug("Creating tasks end. sleep 60 secs...")
            # 봇에서 가동중임을 확인하기 위해 최근 가동시간을 저장
            self.last_tasks_run = dt.datetime.now()
            # 1분간 sleep
            await asyncio.sleep(60)

    def run(self, *args, **kwargs):
        # 대충 loop에 작업 추가하는 파트
        self.loop.create_task(self.tasks())
        # super 실행
        super(DestinyBot, self).run(*args, **kwargs)
