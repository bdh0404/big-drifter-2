import asyncio
import datetime as dt
import json

import discord

import destiny2


class DestinyBot(discord.Client):
    def __init__(self, *, loop=None, **options):
        super(DestinyBot, self).__init__(loop=loop, **options)
        self.d2util = destiny2.ClanUtil(options.pop("bungie_api_key"), options.pop("group_id"), loop=self.loop)
        self.alert_target = options.pop("alert_targets", [])

    async def reload_alert_target(self):
        with open("push_list.json", "r", encoding="utf-8") as f:
            self.alert_target = json.load(f).pop("alert_target")

    async def update_alert_target(self, channel_id):
        # TODO 채팅 통해 업데이트 기능 지원
        pass

    async def msg_members_diff(self, joined: list, leaved: list):
        # TODO 이거 나중가면 필요없을거같은데
        msg_list = list()
        msg_list.append(f"**{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 클랜원 목록 변동 감지!**")
        msg_list.extend(f":blue_circle: {n['destinyUserInfo']['LastSeenDisplayName']} `({n['destinyUserInfo']['membershipId']}, {n['bungieNetUserInfo']['displayName']})`" for n in joined)
        msg_list.extend(f":red_circle: {n['destinyUserInfo']['LastSeenDisplayName']} `({n['destinyUserInfo']['membershipId']}, {n['bungieNetUserInfo']['displayName']})`" for n in leaved)
        return "\n".join(msg_list)

    async def alert(self):
        # 로딩될때까지 대기
        await self.wait_until_ready()
        print(f"Alert task start, {self.is_closed()}")
        while not self.is_closed():
            alert_target = [self.get_channel(id=n) for n in self.alert_target]
            msg_list = []
            # 클랜원 변화 목록 파싱
            joined, leaved = await self.d2util.member_diff()
            # 단순 출력
            if joined or leaved:
                print(f"{dt.datetime.now()} Alert detected: {len(joined)}/{len(leaved)}")
                msg_list.append(await self.msg_members_diff(joined, leaved))

            # TODO joined list 의 member 에 대한 검증 필요
            # Verify code here

            # 대충 메시지 보내는 부분
            msg = "\n\n".join(msg_list)
            for target in alert_target:
                if target is not None and msg:
                    await target.send(msg)
            # 1분간 sleep
            # print(f"loop complete.")
            await asyncio.sleep(60)

    def run(self, *args, **kwargs):
        # 대충 loop에 작업 추가하는 파트
        self.loop.create_task(self.alert())
        # super 실행
        super(DestinyBot, self).run(*args, **kwargs)



