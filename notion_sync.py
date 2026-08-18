"""
collector.py로 수집한 채용공고를 Notion '채용공고 모니터링' DB에 자동으로 입력한다.

사용법:
    python notion_sync.py

동작 방식:
    1. collector.collect_all() 로 최신 공고를 수집
    2. 이미 Notion에 등록된 공고(공고링크 기준)는 건너뛰고, 새 공고만 추가
    3. 유형은 제목에 "인턴"이 있으면 인턴, 없으면 신입으로 임시 분류
       (요구스킬 추출과 함께 나중에 더 정교하게 다듬을 부분)
"""

from __future__ import annotations

import os
from datetime import datetime

import requests
from dotenv import load_dotenv

from collector import collect_all, score_match

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VERSION = "2022-06-28"

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def _to_iso_date(yyyymmdd: str | None) -> str | None:
    """'20260823' 형태를 Notion이 요구하는 '2026-08-23' 형태로 변환."""
    if not yyyymmdd or len(yyyymmdd) != 8:
        return None
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _guess_type(title: str) -> str:
    """제목 텍스트만으로 유형을 임시 분류 (요구스킬 추출 단계에서 더 정교화 예정)."""
    if "인턴" in title:
        return "인턴"
    return "신입"


def already_exists(url: str) -> bool:
    """공고링크 기준으로 이미 등록된 공고인지 확인 (중복 방지)."""
    if not url:
        return False
    query_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    payload = {"filter": {"property": "공고링크", "url": {"equals": url}}}
    resp = requests.post(query_url, headers=HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return len(resp.json().get("results", [])) > 0


def create_page(posting: dict) -> None:
    """공고 1건을 Notion 페이지(DB row)로 생성."""
    title = posting.get("empWantedTitle") or "제목 없음"
    company = posting.get("empBusiNm") or ""
    url = posting.get("empWantedHomepgDetail") or ""
    close_date = _to_iso_date(posting.get("empWantedEndt"))
    match_score = posting.get("matchScore", 0)

    properties = {
        "공고제목": {"title": [{"text": {"content": title}}]},
        "회사": {"rich_text": [{"text": {"content": company}}]},
        "유형": {"select": {"name": _guess_type(title)}},
        "매칭점수": {"number": match_score},
        "상태": {"select": {"name": "신규"}},
    }
    if url:
        properties["공고링크"] = {"url": url}
    if close_date:
        properties["마감일"] = {"date": {"start": close_date}}

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }
    resp = requests.post(
        "https://api.notion.com/v1/pages", headers=HEADERS, json=payload, timeout=10
    )
    resp.raise_for_status()


def sync() -> None:
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        raise RuntimeError("NOTION_API_KEY / NOTION_DATABASE_ID가 .env에 설정되어 있는지 확인하세요.")

    postings = collect_all()
    added, skipped = 0, 0

    for posting in postings:
        posting["matchScore"] = score_match(posting)
        url = posting.get("empWantedHomepgDetail")

        if already_exists(url):
            skipped += 1
            continue

        create_page(posting)
        added += 1
        print(f"추가됨: {posting.get('empBusiNm')} - {posting.get('empWantedTitle')}")

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 동기화 완료 — 신규 {added}건, 중복 스킵 {skipped}건")


if __name__ == "__main__":
    sync()
