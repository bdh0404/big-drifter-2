import asyncio
import datetime as dt
import json
import os
import logging

import pydest


logger = logging.getLogger("d2util")


def str_to_datetime(date_time: str):
    return dt.datetime.fromisoformat(date_time)


class ClanUtil:
    def __init__(self, api_key: str, group_id: int, members_data_path="members.json", loop=None) -> (list, list):
        self.destiny = pydest.Pydest(api_key, loop)
        self.group_id = group_id
        self.members_data_path = members_data_path
        self.members_data_cache = []
        if not os.path.exists(members_data_path):
            with open(members_data_path, "w", encoding="utf-8") as f:
                f.write("[]")

    async def member_diff(self, cmp_file_path="members.json"):
        # 번지 API 서버 요청
        resp = await self.destiny.api.get_members_of_group(self.group_id)
        raw_new: list = resp["Response"]["results"]
        if self.members_data_cache:
            raw_old: list = self.members_data_cache
        else:
            with open(cmp_file_path, "r", encoding="utf-8") as f:
                raw_old: list = json.load(f)
            # 파일도 비어있는 경우 새로 저장한 다음 바로 비어있는 리스트 반환
            if not raw_old:
                with open(cmp_file_path, "w", encoding="utf-8") as f:
                    json.dump(raw_new, f, ensure_ascii=False, indent=2)
                return [], []

        # 집합 변환 후 변화 감지
        set_new = set(n["destinyUserInfo"]["membershipId"] for n in raw_new)
        set_old = set(n["destinyUserInfo"]["membershipId"] for n in raw_old)
        set_joined = set_new - set_old
        set_leaved = set_old - set_new

        # 대상자들 데이터 별도 list 화
        list_joined = [n for n in raw_new if n["destinyUserInfo"]["membershipId"] in set_joined]
        list_leaved = [n for n in raw_old if n["destinyUserInfo"]["membershipId"] in set_leaved]

        # 파일, 메모리에 저장
        self.members_data_cache = raw_new
        with open(cmp_file_path, "w", encoding="utf-8") as f:
            json.dump(raw_new, f, ensure_ascii=False, indent=2)

        # 감지한 사람들 return
        return list_joined, list_leaved

    async def members_offline_time(self, cut_day=21) -> list:
        # 클랜원 목록 불러오기
        resp = await self.destiny.api.get_members_of_group(self.group_id)
        members: list = resp["Response"]["results"]

        # 커트라인 제작
        today = dt.datetime.utcnow().timestamp()
        cut_line = today - cut_day * 86400
        target = [n for n in members
                  if int(n["lastOnlineStatusChange"]) < cut_line]
        target.sort(key=lambda x: x["lastOnlineStatusChange"])      # 보기 쉽게 정렬
        return target

    async def online_members(self):
        resp = await self.destiny.api.get_members_of_group(self.group_id)
        members: list = resp["Response"]["results"]
        online = filter(lambda x: x.get("isOnline"), members)
        return online
