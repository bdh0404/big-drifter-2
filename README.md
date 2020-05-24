# BIG DRIFTER 2
BIG DRIFTER 2 IS WATCHING YOU

## ARCHITECTURE
- `destiny2.py`
  - class `ClanUtil`
    - [x] method `__init__(group_id: int, loop=None)`
    - [x] method `member_diff(file_path: str)`
    - [x] method `member_offline_time(cutline)`
- `bot.py`
  - [ ] class `DestinyBot(discord.Cilent)`
    - [x] method `alert()`: 최종적으로 loop에 등록할 task
    - [x] method `msg_member_diff()`: 멤버 변동 안내 str 생성
    - [ ] method `msg_clean_user()`: 유저 검증 안내 str 생성