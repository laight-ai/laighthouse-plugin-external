---
name: daily-report
description: 라이트하우스(app.laight.ai)의 일간 성과 보고서와 같은 HTML 보고서를 laighthouse MCP 데이터로 만든다. "일간 보고서", "데일리 보고서", "daily 보고서", "어제 성과 보고서" 요청에 사용한다. 기준일 하루를 목표 달성 현황·성과요약·최근 7일 차트·캠페인 진단 트리맵·채널/키워드 표와 AI 제안 카드로 보여 준다. MTD는 mtd-report, 월 마감은 monthly-report.
metadata:
  version: "2.0.0"
---

> ⚡ **thinking 지침**: thinking은 최대한 짧게 유지한다. 바로 아래 순서대로 MCP 호출 → 스크립트 실행 → 완료로 진행한다.

# 라이트하우스 일간 보고서 (daily)

> 🧩 **ChatGPT/Codex 환경**
> - 응답 저장 훅(`hooks/save_responses.py`·`capture_*.py`)은 ChatGPT 데스크톱 Work 모드·Codex에서 `/hooks`로 신뢰했을 때만 돈다.
>   그때는 아래 절차 그대로 동작한다(큰 응답은 저장 안내 한 줄로만 보인다).
> - 스크립트 경로(`assets/…`)는 이 스킬 폴더 기준이다. 결과 파일은 사용자가 내려받을 수 있는 위치(작업 환경의 출력 폴더)에 저장한다.
> - 웹 Chat(스킬 업로드)에는 훅이 없다. `data`의 `missing_responses`에 key가 남으면 받은 응답 원문을 그대로
>   `$WORK/responses/<key>.json`에 저장하고 `data`를 다시 실행한다. 응답이 너무 커서 그대로 저장할 수 없으면 그 key는
>   저장하지 않고(해당 섹션 없이) 진행한다 — 일부만 저장하거나 값을 옮겨 적지 않는다.

app.laight.ai 일간 보고서 화면(`/m/report/{id}`)과 **같은 HTML**을 만든다. 수치·표·차트는 전부 보고서 엔진
(`shared/report_engine/`, 웹앱 보고서와 셀 단위로 일치하게 검증된 산식)이 계산하고, 모델은 **성과요약 텍스트와
AI 제안 카드**만 쓴다. 섹션 구성·텍스트 가이드: `references/guide.md`.

## 절대 원칙

- MCP 응답 숫자를 손으로 옮겨 적거나, 고치거나, 추정하지 않는다. 응답은 플러그인 저장 훅이 파일로 남기고 스크립트가 읽는다 —
  응답 원문·저장 파일을 Read로 열지 않는다(캡처 훅 스텁 `[laighthouse-capture-hook] ... 저장됨`도 무시한다).
- 응답을 못 받은 섹션은 비워 둔다(스크립트가 그 섹션을 빼고 그린다). 다른 기간 값으로 대체하지 않는다.
- HTML·JS를 직접 작성하지 않는다. 항상 `assets/report.py render`로 만든다.
- 텍스트·카드의 숫자는 `data` 출력의 `facts` 값만 쓴다.

> ℹ️ Bash 기본 셸이 `sh`(dash)일 수 있다 — bash 전용 문법은 쓰지 않는다. `python3`이 없으면 `python`으로 부른다.
> `R` = 이 스킬의 `assets/report.py` 절대 경로, `WORK` = `<임시 폴더>/lh-daily-<브랜드>-<D0>`.

## 실행 순서

### 1. 파라미터

- `brand`: 사용자가 말한 브랜드명 그대로(`Unknown brand` 오류일 때만 `get_brand_list`로 확인).
- `D0`: 기준일(미지정 시 어제, KST).
- `author`: 머리글 "작성자"(사용자 이름/아이디, 모르면 이메일 @ 앞부분).

### 2. 호출 계획

```bash
python3 "$R" plan --brand "<brand>" --date <D0> --work "$WORK" --author "<author>"
```
(선택: `--advertiser`, `--created "YYYY-MM-DD HH:MM"`, `--unpublished`, `--brand-color "rgb(…)"`, `--brand-initials`)

출력의 `calls`가 필요한 MCP 호출 전체다(날짜·기간 계산 완료, `metrics` 생략 = 서빙 지표 전부). `date_error`가 나오면 그 문구를 알리고 멈춘다.

### 3. 데이터 호출 — 한 메시지에 동시 발사

`calls`를 **params 그대로**(값·키를 바꾸지 말 것) 모두 병렬 호출한다. 응답은 읽지 않는다.

### 4. 데이터 생성 + 요약 수치

```bash
python3 "$R" data --work "$WORK"
```

출력 한 줄 JSON: `report_name`, `missing_responses`(다시 보낼 호출 — params 포함), `text_slots_to_write`, `facts`(텍스트 근거).
- `missing_responses`가 있으면 그 호출만 **거기 적힌 params 그대로** 다시 보내고(목표 호출에 지표 이름이 붙어 나올 수 있다 —
  브랜드 지표 이름이 서버 기본값과 다를 때) `data`를 다시 실행한다. 크기 오류로 계속 실패하면 그 섹션 없이 진행한다.
  도구 오류(목표 없음 등)는 다시 보내지 않는다. `list_promotions`의 `Promotion calendar is not enabled`는 그대로 둔다(프로모션 없음).
- 저장 훅이 없는 호스트라 계속 빠지면 받은 응답 원문을 그대로 `$WORK/responses/<key>.json`에 저장한다(호스트가 파일로 돌렸다는
  안내 `Output has been saved to <path>`가 있으면 `cp <path>`). 숫자를 고치거나 행을 빼지 않는다.

### 5. 텍스트·AI 제안 작성 → 렌더링 (1회)

`facts`만 근거로 `references/guide.md`대로 쓰고, **파일을 따로 만들지 말고** 바로 render의 stdin으로 넘긴다:

```bash
python3 "$R" render --work "$WORK" --out "<경로>" <<'EOF'
{"texts": {"daily_executive_summary": "- ...\n- ..."},
 "action_cards": [{"title": "...", "tags": ["예산"], "description": "...", "actions": ["..."], "background": "• ...\n• ..."}]}
EOF
```

- `texts`의 키 = `text_slots_to_write`. 쓰지 않은 슬롯은 섹션이 빠진다. `action_cards`는 우측 "AI 제안" 패널(보통 2개).
- 텍스트는 웹앱과 같은 마크다운(GFM, 줄바꿈 = `<br>`). 밑줄이 든 이름(`01_분말`)은 마크다운 `\_` — JSON 문자열에서는 `\\_`.
- `<경로>`: 사용자가 지정한 경로, 없으면 `~/Downloads/laighthouse-reports/<brand>_daily_<D0>.html`.
- 숫자 표기: 금액은 만 원 단위 반올림("약 3억 8,800만 원", 1만 원 미만은 원), 비율은 facts `*_pct`를 소수 1자리(천 단위 쉼표),
  차이는 `%p`, 증감률은 `%`, CPC는 원 단위 정수, 날짜는 "10월 11일". ROAS 목표는 facts `target.roas.target_pct`.

### 6. 전달

결과는 단독으로 열리는 HTML 한 파일이다(폰트만 CDN). 채팅에서 보여 줄 수 있는 호스트(Artifact 등)면 그 파일로 게시한다.
완료 메시지:

```
{report_name} 생성 완료.
파일: {out}
가장 인상적인 부분: {한 문장 하이라이트}.
— by LaightAI
```
