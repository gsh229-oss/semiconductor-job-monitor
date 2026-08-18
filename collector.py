"""
워크넷(고용24) '공채속보' API에서 반도체 관련 채용공고를 수집하는 스크립트.

※ 처음엔 '채용정보목록' API(callOpenApiSvcInfo210L01.do)로 시도했으나
   개인 인증키는 접근이 막혀있는 것을 확인(<error>개인회원은 사용할 수 없는
   OPEN-API입니다.</error>). 그래서 개인도 쓸 수 있는 '공채속보' API
   (callOpenApiSvcInfo210L21.do)로 전환했습니다. 이 API는 대기업/공공기관 등의
   공채 소식 위주라, 중소기업 상시채용까지는 못 잡을 수 있습니다.

사용법:
    1. .env.example 을 .env 로 복사하고 WORK24_AUTH_KEY 값 채우기
    2. pip install -r requirements.txt
    3. python collector.py

참고:
    출력 XML의 정확한 태그명을 100% 확정하지 못해서, 태그명을 하드코딩하지 않고
    'empWantedTitle' 또는 'coNm' 같은 알려진 필드가 들어있는 노드를 자동으로
    찾아서 그 안의 모든 하위 태그를 그대로 dict로 변환하는 방식으로 짰습니다.
    처음 실행하면 실제로 어떤 필드들이 나오는지 그대로 출력되니, 그걸 보고
    다음 단계(Notion 연동)에서 필요한 필드만 골라 쓰면 됩니다.
"""

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

AUTH_KEY = os.getenv("WORK24_AUTH_KEY")
BASE_URL = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L21.do"

# 반도체 관련 공고를 걸러내기 위한 1차 키워드 (채용제목 기준 검색).
# 국내 일반 키워드 + 외국계 반도체 장비사 키워드를 함께 검색.
# 'engineer' 처럼 너무 범용적인 단어는 무관한 공고까지 다 걸려서 일부러 뺐습니다.
SEMICONDUCTOR_KEYWORDS = [
    "반도체",
    "웨이퍼",
    "파운드리",
    "반도체장비",
    "세미콘",
    "ASML",
    "Applied Materials",
    "Lam Research",
    "KLA",
    "Tokyo Electron",
    "TEL",
    "Entegris",
    "Advantest",
]

# 경력구분: 30=신입, 40=인턴 (다중검색, | 로 구분)
CAREER_FILTER = "30|40"

# 이 필드들 중 하나라도 자식으로 가진 노드를 "채용정보 레코드"로 인식한다.
# (실제 응답 확인 결과: 회사명=empBusiNm, 마감일=empWantedEndt, 상세URL=empWantedHomepgDetail)
RECORD_MARKER_TAGS = {"empWantedTitle", "empBusiNm", "empWantedHomepgDetail"}

# 매칭점수 계산에 쓸 본인 스킬 목록 (5단계에서 이 부분을 더 정교하게 다듬을 예정)
MY_SKILLS = {"Python", "데이터분석", "반도체공정", "TCAD", "FDC"}


def fetch_postings(keyword: str, start_page: int = 1, display: int = 100) -> list[dict]:
    """워크넷 공채속보 API를 호출해 공고 목록을 가져온다."""
    if not AUTH_KEY:
        raise RuntimeError("WORK24_AUTH_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    params = {
        "authKey": AUTH_KEY,
        "callTp": "L",
        "returnType": "XML",
        "startPage": start_page,
        "display": display,
        "empWantedTitle": keyword,
        "empWantedCareerCd": CAREER_FILTER,
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)

    # 에러 응답인지 먼저 확인 (예: 개인회원 제한, 인증키 오류 등)
    error_el = root.find(".//error")
    if error_el is not None and error_el.text:
        raise RuntimeError(f"API 오류 응답: {error_el.text}")

    return _extract_records(root)


def _extract_records(root: ET.Element) -> list[dict]:
    """태그명을 몰라도, 알려진 필드를 포함한 반복 노드를 찾아 dict 리스트로 변환."""
    records = []
    for node in root.iter():
        children = list(node)
        if not children:
            continue
        child_tags = {child.tag for child in children}
        if child_tags & RECORD_MARKER_TAGS:
            record = {child.tag: (child.text or "").strip() for child in children}
            records.append(record)
    return records


def collect_all() -> list[dict]:
    """여러 키워드로 검색한 결과를 합치고 중복 제거 (회사명+제목 기준)."""
    seen: dict[tuple, dict] = {}
    for kw in SEMICONDUCTOR_KEYWORDS:
        for posting in fetch_postings(kw):
            key = (posting.get("empBusiNm"), posting.get("empWantedTitle"))
            seen[key] = posting
    return list(seen.values())


def score_match(posting: dict) -> float:
    """
    임시 매칭점수 함수 (5단계에서 정교화 예정).
    지금은 채용제목에 본인 스킬 키워드가 몇 개 들어있는지로 간단히 계산.
    나중에 임베딩 기반 코사인 유사도로 교체합니다.
    """
    title = posting.get("empWantedTitle") or ""
    hits = sum(1 for skill in MY_SKILLS if skill.lower() in title.lower())
    return round(hits / len(MY_SKILLS), 2)


if __name__ == "__main__":
    results = collect_all()
    for r in results:
        r["matchScore"] = score_match(r)

    print(f"수집된 공고 수: {len(results)}건")
    if results:
        print("\n[첫 번째 결과의 필드 구조 확인용]")
        print(json.dumps(results[0], ensure_ascii=False, indent=2))

    print("\n[매칭점수 상위 5개]")
    for r in sorted(results, key=lambda x: x["matchScore"], reverse=True)[:5]:
        company = r.get("empBusiNm", "?")
        title = r.get("empWantedTitle", "?")
        close_dt = r.get("empWantedEndt", "?")
        print(f"[{r['matchScore']}] {company} - {title} (마감: {close_dt})")

    # 로컬 확인용으로 JSON 저장 (Notion 연동은 6단계에서 추가 예정)
    out_path = f"postings_{datetime.now().strftime('%Y%m%d')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과를 {out_path} 에 저장했습니다.")
