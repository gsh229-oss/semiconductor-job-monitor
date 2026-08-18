# 로컬 실행 가이드

## 1. 파일 준비
이 4개 파일을 GitHub 저장소(semiconductor-job-monitor)에 추가하세요:
- requirements.txt
- .env.example
- .gitignore
- collector.py

## 2. 환경변수 설정
```bash
cp .env.example .env
```
`.env` 파일을 열어서 `WORK24_AUTH_KEY=` 뒤에 발급받은 인증키를 붙여넣으세요.

## 3. 패키지 설치
```bash
pip install -r requirements.txt
```

## 4. 실행
```bash
python collector.py
```

## 5. 결과 확인
- 터미널에 매칭점수 상위 5개 공고가 출력됩니다.
- `postings_날짜.json` 파일에 전체 결과가 저장됩니다 (이 파일은 .gitignore에 포함되어 있어 커밋되지 않습니다).

## 만약 오류가 난다면
- **403 / 인증 오류**: 개인 인증키는 채용정보목록 API가 제한되어 있을 수 있습니다. 이 경우 워크넷 사이트 "서비스 소개 및 신청" 페이지에서 "공채속보" 또는 "공채기업정보" 탭을 열어 정확한 요청 URL과 파라미터 표를 캡처해서 공유해주세요 — 그 스펙에 맞춰 collector.py를 다시 짜드릴게요.
- **키워드 결과가 0건**: `SEMICONDUCTOR_KEYWORDS` 리스트의 키워드를 조정해보세요.

## Git으로 저장소에 추가하기
터미널에서 저장소 폴더로 이동한 뒤:
```bash
git add requirements.txt .env.example .gitignore collector.py SETUP.md
git commit -m "채용공고 수집 스크립트 초안 추가"
git push
```
