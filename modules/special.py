import asyncio
import logging
from collections.abc import AsyncIterator, Iterable, Iterator, Mapping
from datetime import datetime, timedelta
from random import choice
from typing import Any, Literal, Optional

from modules.util import SessionType, browser_agent, request
from storeInfo import Store

COMMENTS: dict[str, dict[str, str]] = {}
dayOfWeek = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def convert(dct: Mapping[str, Any], userLang: bool = True) -> str:
	match dct:
		case {"closed": True}:
			return "不营业" if userLang else "Closed"
		case {"openTime": "00:00", "closeTime": "23:59"}:
			return "24 小时营业" if userLang else "Always Open"
		case {"openTime": opt, "closeTime": clt}:
			return f'{opt} - {clt}'
		case _:
			return "未知时间" if userLang else "Unknown Hours"

def ignored(
	data: list[dict[str, Any]],
	rules: dict[str, str],
	userLang: bool = True) -> Iterator[tuple[str, str]]:
	for item in sorted(data, key = lambda k: k["date"]):
		converted = convert(item, userLang)
		try:
			for key in ("date", "name"):
				assert converted != rules.get(item[key])
		except:
			continue
		yield item["date"], converted

async def apu(store: Store, userLang: bool, target: str,
	session: Optional[SessionType] = None) -> AsyncIterator[tuple[str, str, str]]:
	retry = 3
	base = f"https://www.apple.com{store.region.url_store}"
	url = f"{base}/shop/fulfillment-messages"
	referer = browser_agent | {"Referer": f"{base}/shop/product/{target}"}
	params = {"searchNearby": "true", "store": store.rid, "parts.0": target}

	stores: list[dict] = []
	while retry:
		try:
			r = await request(url, session, headers = referer, timeout = 5,
				params = params, raise_for_status = True, mode = "json")
			stores = r["body"]["content"]["pickupMessage"]["stores"]
			break
		except:
			retry -= 1
			sec = choice(list(range(2, 16, 2)))
			logging.debug(("等待 {} 秒" if userLang else "Waiting {} sec").format(sec))
			await asyncio.sleep(sec)

	for rstore in stores:
		for holiday in rstore["retailStore"]["storeHolidays"]:
			raw = datetime.strptime(f"{holiday["date"]} 00", "%b %d %y").replace(year = datetime.now().year)
			if raw < datetime.now() - timedelta(weeks = 1):
				raw = raw.replace(year = raw.year + 1)
			text = " ".join([f"[{holiday["description"]}]" if holiday["description"] else "", holiday["comments"] or ""])
			yield (rstore["storeNumber"], f"{raw:%F}", text)

async def comment(store: Store, userLang: bool = True,
	accepted_dates: Iterable[str] = [],
	session: Optional[SessionType] = None) -> dict[str, dict[str, str]]:
	async for s, d, t in apu(store, userLang, f'MM0A3{store.region.part_sample}/A', session):
		if accepted_dates and d not in accepted_dates:
			continue
		COMMENTS.setdefault(s, {})[d] = t
	return COMMENTS

async def special(store: Store, *,
	threshold: Optional[datetime] = None,
	ask_comment: bool = True,
	userLang: bool = True,
	detail: dict[str, list[dict[str, Any]]] = {},
	rules: dict[str, str] = {},
	session: Optional[SessionType] = None) -> Optional[dict[str, dict[str, str]]]:
	threshold = threshold or datetime.now()
	if not detail:
		try:
			detail = await store.detail(session = session, mode = "hours")
			assert isinstance(detail, dict)
			for key in ("regular", "special"):
				assert key in detail
		except:
			text = f"未能获得 {store.rid} 营业时间信息" if userLang else f"Failed getting store hours for {store.rid}"
			logging.getLogger("modules.special").error(text)
			return

	comments, results, asked = {}, {}, []
	regular = {dayOfWeek.index(regular["name"]): convert(regular, userLang = userLang) for regular in detail["regular"]}
	for date, converted in ignored(detail["special"], rules = rules, userLang = userLang):
		d = datetime.strptime(date, "%Y-%m-%d")
		if date < f"{threshold:%F}":
			continue
		reg = regular[d.weekday()]
		try:
			assert ask_comment
			assert store.rid not in comments
			assert store.rid not in asked
			comments = await comment(store, userLang, session = session)
		except:
			pass
		finally:
			asked.append(store.rid)
		com = comments.get(store.rid, {}).get(date)
		results[f"{d:%F}"] = {"regular": reg, "special": converted} | ({"comment": com} if com else {})
	return results

type ResultType = tuple[str, Literal["new", "change", "comment", "outdated", "cancel"], *tuple[str, ...]]

def compare(
	original: dict[str, dict[str, str]],
	current: dict[str, dict[str, str]],
	threshold: str = "") -> list[ResultType]:
	diff: list[ResultType] = []
	for date, detail in current.items():
		spe = detail["special"]
		if date < threshold:
			continue
		if date not in original:
			diff.append((date, "new", spe))
		elif (svd := original[date]["special"]) != spe:
			diff.append((date, "change", svd, spe))
		elif not original[date].get("comment") and detail.get("comment"):
			diff.append((date, "comment", detail["comment"]))
	for date, detail in original.items():
		if date < threshold:
			diff.append((date, "outdated"))
		elif date not in current:
			diff.append((date, "cancel", detail["special"]))
	return sorted(diff)