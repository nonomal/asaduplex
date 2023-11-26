import asyncio
import json
import logging
from bot import chat_ids
from botpost import async_post, photo_encode
from datetime import datetime
from modules.util import SemaphoreType, SessionType
from modules.util import disMarkdown, request, session_func, setLogger
from storeInfo import Store, StoreDict, sidify
from sys import argv
from typing import Optional, cast

INVALIDS = [datetime(2021, 7, 13), datetime(2021, 8, 28),
	datetime(2021, 8, 29), datetime(2022, 1, 7)]

async def task(store: Store, session: SessionType, semaphore: SemaphoreType) -> Optional[tuple[datetime, bool]]:
	try:
		async with semaphore:
			r = await request(store.dieter, session, method = "HEAD",
				mode = ["status", "head"], retry = 3, allow_redirects = False)
		assert r["status"] == 200
		assert "Last-Modified" in r["head"]
	except AssertionError:
		return None
	except Exception as exp:
		logging.error(f"[{store.rid}] 请求失败: {exp!r}")
		return None

	local_format = "%Y-%m-%d %H:%M:%S"
	remote_format = "%a, %d %b %Y %H:%M:%S GMT"
	local = datetime.strptime(store.modified, local_format) if hasattr(store, "modified") else datetime(2001, 5, 19)
	remote = datetime.strptime(r["head"]["Last-Modified"], remote_format)

	if remote > local:
		invalid = any(all(getattr(inv, key) == getattr(remote, key) for key in ("year", "month", "day")) for inv in INVALIDS)
		return remote, invalid

async def post(store: Store, dt: datetime, session: SessionType, semaphore: SemaphoreType) -> None:
	async with semaphore:
		r = await request(store.dieter, session, mode = "raw", retry = 3)
	with open(f"Retail/{store.rid}-{dt:%F-%H%M%S}.png", "wb") as w:
		w.write(r)
	texts = ["*零售店图片更新通知*", "", store.telename(True, True, True), f"*远程标签* {dt:%F %T}"]
	if hasattr(store, "modified"):
		texts.insert(-1, f"*本地标签* {store.modified}")
	photo = photo_encode(r)
	buttons = [[["启动消息推送向导", f"RTLPOST {store.sid} NEW"]]]
	await async_post({
		"mode": "photo-text",
		"image": photo,
		"text": disMarkdown("\n".join(texts)),
		"chat_id": chat_ids[0],
		"keyboard": buttons,
		"parse": "MARK"})

async def entry(store: Store, pointer: dict[str, StoreDict], lists: list[str],
	session: SessionType, semaphore: SemaphoreType) -> bool:
	special = store.sid in lists
	result = await task(store, session, semaphore)
	if not result:
		if special:
			logging.info(f"[{store.rid}] 图片没有更新")
		return False
	else:
		rem, inv = result
		logging.info(f"[{store.rid}] 图片有{"无效" if inv else ""}更新: {rem:%F %T}")
		if special:
			lists.remove(store.sid)
		pointer[store.sid]["modified"] = f"{rem:%F %T}"
		pointer[store.sid] = cast(StoreDict, dict(sorted(pointer[store.sid].items())))
		if not inv:
			try:
				logging.info(f"[{store.rid}] 准备下载和发送消息")
				await post(store, rem, session, semaphore)
			except Exception as exp:
				logging.warning(f"[{store.rid}] 下载或发送失败: {exp!r}")
		return True

@session_func
async def main(session: SessionType) -> None:
	semaphore = asyncio.Semaphore(50)
	with open("storeInfo.json") as r:
		j = json.load(r)
		p = cast(dict[str, StoreDict], j)

	mode = argv[1:] or ["normal"]
	match mode:
		case ["normal" | "single" as mode, *ids]:
			sids, l = [sidify(i) for i in ids], []
			stores = [Store(s, d) for s, d in p.items() if mode == "normal" or s in sids]
		case ["special"]:
			with open("specialists.json") as r:
				l = cast(list[str], json.load(r))
			stores = [Store(s, d) for s, d in p.items() if s in l]
		case _:
			stores, l = [], []

	logging.info(f"准备查询 {len(stores)} 家零售店")
	tasks = [entry(store, p, l, session, semaphore) for store in stores]
	if any(await asyncio.gather(*tasks)):
		j["update"] = dt = f"{datetime.now():%F %T}"
		if mode[0] == "special":
			logging.info(f"更新特别观察列表: {l}")
			with open("specialists.json", "w") as w:
				json.dump(l, w, ensure_ascii = False, indent = 2)
		logging.info(f"更新门店数据文件: {dt}")
		with open("storeInfo.json", "w") as w:
			json.dump(p, w, ensure_ascii = False, indent = 2)

setLogger(logging.INFO, __file__, base_name = True)
asyncio.run(main())
logging.info("程序结束")