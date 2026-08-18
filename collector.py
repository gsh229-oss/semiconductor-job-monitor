"""
워크넷(고용24) 채용정보 API에서 반도체 관련 채용공고를 수집하는 스크립트.

사용법:
    1. .env.example 을 .env 로 복사하고 WORK24_AUTH_KEY 값 채우기
    2. pip install -r requirements.txt
    3. python collector.py

주의:
    - 개인 인증키는 '채용정보목록/상세' API 접근이 제한될 수 있습니다.
      이 스크립트를 실행했을 때 인증 오류(403 등)가 나면, 워크넷 사이트의
      '서비스 소개 및 신청' 페이지에서 공채속보/공채기업정보 탭의 정확한
      요청 URL과 파라미터를 확인해서 알려주세요. 그에 맞춰 코드를 다시 짜드립니다.
"""

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

AUTH_KEY = os.getenv("WORK24_AUTH_KEY")
BASE_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"

# 반도체 관련 공고를 걸러내기 위한 1차 키워드.
# 실제 돌려보면서 회사 이름이 자꾸 빠지거나 노이즈가 많으면 이 리스트를 조정하면 됩니다.
SEMICONDUCTOR_KEYWORDS = ["반도체", "웨이퍼", "파운드리", "공정엔지니어", "반도체공정"]

# 매칭점수 계산에 쓸 본인 스킬 목록 (5단계에서 이 부분을 더 정교하게 다듬을 예정)
MY_SKILLS = {"Python", "데이터분석", "반도체공정", "TCAD", "FDC"}


def fetch_postings(keyword: str, start_page: int = 1, display: int = 100) -> list[dict]:
    """워크넷 채용정보 API를 호출해 공고 목록을 가져온다."""
    if not AUTH_KEY:
        raise RuntimeError("WORK24_AUTH_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    params = {
        "authKey": AUTH_KEY,
        "callTp": "L",
        "returnType": "XML",
        "startPage": start_page,
        "display": display,
        "keyword": keyword,
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    postings = []
    for wanted in root.findall(".//wanted"):
        postings.append(
            {
                "wantedAuthNo": _text(wanted, "wantedAuthNo"),
                "company": _text(wanted, "company"),
                "title": _text(wanted, "title"),
                "region": _text(wanted, "region"),
                "career": _text(wanted, "career"),
                "minEdubg": _text(wanted, "minEdubg"),
                "regDt": _text(wanted, "regDt"),
                "closeDt": _text(wanted, "closeDt"),
                "empTpCd": _text(wanted, "empTpCd"),
                "wantedInfoUrl": _text(wanted, "wantedInfoUrl"),
            }
        )
    return postings


def _text(node: ET.Element, tag: str):
    el = node.find(tag)
    return el.text if el is not None else None


def collect_all() -> list[dict]:
    """여러 키워드로 검색한 결과를 합치고, 구인인증번호 기준으로 중복 제거."""
    seen: dict[str, dict] = {}
    for kw in SEMICONDUCTOR_KEYWORDS:
        for posting in fetch_postings(kw):
            seen[posting["wantedAuthNo"]] = posting
    return list(seen.values())


def score_match(posting: dict) -> float:
    """
    임시 매칭점수 함수 (5단계에서 정교화 예정).
    지금은 채용제목에 본인 스킬 키워드가 몇 개 들어있는지로 간단히 계산.
    나중에 임베딩 기반 코사인 유사도로 교체합니다.
    """
    title = posting.get("title") or ""
    hits = sum(1 for skill in MY_SKILLS if skill.lower() in title.lower())
    return round(hits / len(MY_SKILLS), 2)


if __name__ == "__main__":
    results = collect_all()
    for r in results:
        r["matchScore"] = score_match(r)

    print(f"수집된 공고 수: {len(results)}건")
    for r in sorted(results, key=lambda x: x["matchScore"], reverse=True)[:5]:
        print(f"[{r['matchScore']}] {r['company']} - {r['title']} (마감: {r['closeDt']})")

    # 로컬 확인용으로 JSON 저장 (Notion 연동은 6단계에서 추가 예정)
    out_path = f"postings_{datetime.now().strftime('%Y%m%d')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"결과를 {out_path} 에 저장했습니다.")
