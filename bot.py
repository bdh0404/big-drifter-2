import asyncio
import datetime as dt
import json
import logging

import discord

import destiny2


logger = logging.getLogger("bot")


class DestinyBot(discord.Client):
    def __init__(self, *, loop=None, **options):
        super(DestinyBot, self).__init__(loop=loop, **options)
        self.d2util = destiny2.ClanUtil(options.pop("bungie_api_key"), options.pop("group_id"), loop=self.loop)
        self.st = dt.datetime.now()
        self.offline_cut = options.pop("offline_cut", 14)
        self.last_tasks_run = None
        with open("push_list.json", "r", encoding="utf-8") as f:
            self.alert_target: list = json.load(f).pop("alert_target", [])

        if not self.alert_target:
            logger.warning("Empty alert target list!!")

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

    async def toggle_alert_target(self, channel_id: int):
        if channel_id in self.alert_target:
            self.alert_target.remove(channel_id)
            ret = 0
        else:
            self.alert_target.append(channel_id)
            ret = 1
        await self.update_alert_target()
        return ret

    async def get_uptime(self):
        return str(dt.datetime.now() - self.st)

    async def get_long_offline(self, offline_cut=0):
        cut = offline_cut if offline_cut else self.offline_cut
        # target: 유저 정보 담긴 dict 객체들의 list
        target = await self.d2util.members_offline_time(cut)
        data = [{'display_name': n['destinyUserInfo']['LastSeenDisplayName'],
                 'membership_id': n['destinyUserInfo']['membershipId'],
                 'bungie_name': n.get('bungieNetUserInfo', {}).get('displayName', ""),
                 'last_online': dt.timedelta(seconds=int(dt.datetime.utcnow().timestamp()) - int(n['lastOnlineStatusChange']))}
                for n in target]
        msg_list = list()
        msg_list.append(f"**{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 기준 {cut}일 이상 미접속자 목록**")
        msg_list.extend(f"**{n['display_name']}**`({n['membership_id']}, {n['bungie_name']})`\n`{n['last_online']}`" for n in data)
        return "\n".join(msg_list)

    async def msg_members_diff(self, joined: list, leaved: list):
        # TODO 이거 나중가면 필요없을거같은데
        msg_list = list()
        msg_list.append(f"**{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 클랜원 목록 변동 감지!**")
        msg_list.extend(f":blue_circle: **{n['destinyUserInfo']['LastSeenDisplayName']}** `({n['destinyUserInfo']['membershipId']}, {n['bungieNetUserInfo']['displayName']})`" for n in joined)
        msg_list.extend(f":red_circle: **{n['destinyUserInfo']['LastSeenDisplayName']}** `({n['destinyUserInfo']['membershipId']}, {n['bungieNetUserInfo']['displayName']})`" for n in leaved)
        return "\n".join(msg_list)

    async def alert(self):
        logger.debug("Alert Task start!")
        alert_target = [self.get_channel(id=n) for n in self.alert_target]
        msg_list = []
        # 클랜원 변화 목록 파싱
        joined, leaved = await self.d2util.member_diff()
        # 단순 출력
        if joined or leaved:
            logger.info(f"{dt.datetime.now()} Alert detected: {len(joined)}, {len(leaved)}")
            msg_list.append(await self.msg_members_diff(joined, leaved))

        # TODO joined list 의 member 에 대한 검증 필요
        # Verify code here

        # 대충 메시지 보내는 부분
        msg = "\n\n".join(msg_list)
        for target in alert_target:
            if target is not None and msg:
                await target.send(msg)
        logger.debug("Alert Task end")

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



