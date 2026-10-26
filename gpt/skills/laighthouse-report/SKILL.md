---
name: laighthouse-report
description: 라이트하우스(app.laight.ai)의 일간·MTD·월 마감 성과 보고서와 동일한 HTML 보고서를 laighthouse MCP 데이터로 생성한다. "일간/데일리 보고서", "MTD 보고서", "월간/월 마감 보고서", "라이트하우스 보고서 HTML로 만들어줘" 같은 요청에 사용한다. 웹앱 보고서 화면과 같은 섹션 구성·수치 산식·문구·디자인(CSS, 차트, 트리맵, 계층 표, AI 제안 카드)으로 단일 HTML 파일을 만든다.
---

# 라이트하우스 보고서 HTML 생성

> 🧩 **ChatGPT/Codex 환경**
> - 응답 저장 훅(`hooks/save_mcp_response.py`)은 ChatGPT 데스크톱 Work 모드·Codex에서 `/hooks`로 신뢰했을 때만 돈다.
>   그때는 아래 절차 그대로 동작한다(큰 응답은 저장 안내 한 줄로만 보인다).
> - 웹 Chat(스킬 업로드)에는 훅이 없다. `data`의 `missing_responses`에 key가 남으면 4단계의 "직접 저장" 방법으로
>   받은 응답을 `$WORK/responses/<key>.json`에 저장한다. `(대용량)` 표시가 있는 호출의 응답이 너무 커서 그대로
>   저장할 수 없으면 그 key는 저장하지 않고(해당 섹션 없이) 진행한다 — 일부만 저장하거나 값을 옮겨 적지 않는다.
> - `ASSETS`는 이 스킬 폴더의 `assets/` 절대 경로, `WORK`는 쓰기 가능한 임시 폴더다. 결과 HTML은 사용자가 내려받을
>   수 있는 위치(작업 환경의 출력 폴더)에 저장한다.

app.laight.ai의 보고서 조회 화면(`/m/report/{id}`)과 **같은 HTML**을 만든다. 웹앱이 쓰는 보고서 데이터
형식(`analysis-artifact` 목록)을 MCP 데이터로 똑같이 계산하고, 웹앱의 섹션 컴포넌트를 그대로 옮긴
렌더러(`assets/report.js` + 웹앱 CSS `assets/app.css`)로 그린다.

| 보고서 | 기준 | 웹앱 이름 예시 | 상세 |
|---|---|---|---|
| `daily` (일간) | 기준일 D0 하루 + 최근 7일·30일 | `2026년 10월 11일 라형식품 일간 보고서` | `references/daily.md` |
| `mtd` | 당월 1일 ~ 기준일 누적 | `26.10.01 ~ 26.10.11 라형식품 MTD 보고서` | `references/mtd.md` |
| `monthly` (월 마감) | 마감된 한 달 | `2026년 9월 라형식품 월 마감 보고서` | `references/monthly.md` |

수치·표·차트는 전부 `assets/build_report.py`가 계산한다(웹앱 보고서와 셀 단위로 일치하는 것을 검증한 산식).
모델이 쓰는 것은 **텍스트 섹션과 AI 제안(액션 카드)** 뿐이다.

## 절대 원칙

- MCP 응답 숫자를 손으로 옮겨 적거나, 고치거나, 추정하지 않는다. 응답은 파일로 넘긴다(4단계).
- 응답을 못 받은 섹션은 비워 둔다(스크립트가 그 섹션을 빼고 그린다). 다른 기간 값으로 대체하지 않는다.
- HTML·JS를 직접 작성하지 않는다. 항상 `build_report.py render`로 만든다.
- 텍스트·액션 카드의 숫자는 `facts.json`(필요하면 `data.json`) 값만 쓴다. facts에 없는 수치가 필요하면
  같은 MCP로 추가 조회한 응답에서만 가져온다.

## 실행 순서

작업 폴더를 정한다: `WORK=<임시 폴더>/lh-<type>-<date>`. `ASSETS`는 이 스킬의 `assets/` 절대 경로.

### 1. 파라미터

- `brand`: 사용자가 말한 브랜드명 그대로(`Unknown brand` 오류일 때만 `get_brand_list`로 확인).
- `type`: daily / mtd / monthly.
- `date`: daily는 기준일 D0(미지정 시 어제, KST), mtd는 누적 종료일(미지정 시 어제), monthly는 `YYYY-MM`
  (미지정 시 지난달).
- `author`: 머리글 "생성 … · 작성자"에 쓰일 사용자 이름/아이디(모르면 이메일 @ 앞부분).
- `advertiser`: 월 마감 표지에서 브랜드 아래 줄(조직/광고주명). 모르면 생략.

### 2. 응답 저장 켜기 → 디스커버리 호출 (1회)

첫 MCP 호출 **전에** 응답 저장을 켠다. 플러그인 훅은 이 표시가 있는 세션(3시간)에서만 응답을 저장한다.

```bash
python3 "$ASSETS/build_report.py" arm
```

`get_ad_performance(brand_name, start_date=S, end_date=E, time_grain="total", group_by=["media"])` — **`metrics` 생략**.
S·E는 daily/mtd면 `date`(하루), monthly면 그 달의 1일·말일.

### 3. 호출 계획

```bash
python3 "$ASSETS/build_report.py" plan --type <type> --brand "<brand>" --date <date> \
  --discovery auto --work "$WORK" --author "<author>" [--advertiser "<org>"]
```

- `--discovery auto`는 플러그인 훅이 저장해 둔 디스커버리 응답을 찾는다. "no captured discovery" 오류가 나면
  디스커버리 응답 원문을 `$WORK/discovery.json`에 저장하고 `--discovery "$WORK/discovery.json"`으로 다시 실행한다.
- 기타 옵션: `--created "YYYY-MM-DD HH:MM"`(머리글 생성 시각, 기본 현재 KST), `--unpublished`(머리글 배지를
  "미공개"로, 기본 "공개"), `--brand-color "rgb(…)"`, `--brand-initials "라형"`(월 마감 표지 브랜드 타일).

출력의 `calls`가 필요한 MCP 호출 전체다(날짜·지표 키·매체 목록 계산 완료). `ctx_`로 시작하는 key는 텍스트
작성용 보조 데이터(권장)다.

### 4. MCP 호출 → 데이터 생성

`calls`를 **params 그대로**(값·키를 바꾸지 말 것) 한 메시지에서 병렬 호출한다. 응답은 읽지 않는다 — 플러그인 훅
(`hooks/save_mcp_response.py`)이 `arm` 이후의 응답을 원문 그대로 저장하고, 큰 응답은 모델에게 `[laighthouse-report]
응답 원본(…)을 저장했다` 한 줄로만 보여 준다. 응답이 다 오면 바로:

```bash
python3 "$ASSETS/build_report.py" data --work "$WORK"
```

`data`가 먼저 **현재 세션에서 저장된 응답 중** 도구·인자가 같은 것을 `$WORK/responses/<key>.json`으로 모은 뒤
(따로 `collect`를 부를 필요 없음) `$WORK/data.json`(보고서 데이터)과 `$WORK/facts.json`(텍스트용 요약 수치)을 만든다.
훅은 MCP 서버 이름과 무관하게(플러그인 서버·claude.ai 커넥터 모두) 동작하고, 호스트가 큰 응답을 파일로 돌린 경우
(`exceeds maximum allowed tokens. Output has been saved to <path>`)에도 그 파일의 원문을 가져온다. 매체별 월 예산은
`target` 응답의 두 번째 표(매체별 목표)에서 읽는다 — 매체마다 목표를 따로 부르지 않는다.

출력의 `missing_responses`에 남은 key만:
- 그 호출을 다시 보내고 `data`를 다시 실행한다.
- 그래도 저장되지 않으면(훅이 없는 환경) 받은 응답을 직접 저장한다: 호스트가 파일로 돌렸다는 안내(`Output has been
  saved to <path>`)가 있었으면 `cp <path> "$WORK/responses/<key>.json"`(안내문 자체는 저장하지 않는다), 아니면 받은
  응답 텍스트를 그대로 따옴표 heredoc으로 쓴다(`cat > "$WORK/responses/<key>.json" <<'EOF'` … `EOF`). 숫자를 고치거나
  행을 빼지 않는다.
- 도구 오류는 저장하지 않는다(그 섹션 없이 진행). 단 `list_promotions`의 `Promotion calendar is not enabled` 오류는
  `[]`를 저장.

### 5. 텍스트·AI 제안 작성

`facts.json`을 읽고 `references/<type>.md`의 가이드대로 `$WORK/texts.json`을 쓴다. facts.json이 커서 셸 출력이 잘리면
Read 도구로 연다. texts.json은 **Write 도구로** 쓴다 — 셸 heredoc·sed로 쓰면 `\_` 같은 백슬래시가 바뀌어 JSON이 깨진다
(JSON 문자열 안에서는 `\\_`로 적는다).

```json
{
  "texts": { "<slot_key>": "마크다운 문자열" },
  "action_cards": [
    { "title": "...", "tags": ["예산"], "description": "...", "actions": ["...", "..."], "background": "• ...\n• ..." }
  ]
}
```

- `texts`의 키 = 4단계 `data` 출력의 `text_slots_to_write`. 쓰지 않은 슬롯은 섹션이 빠진다.
- `action_cards`는 daily·mtd만(우측 "AI 제안" 패널). monthly는 쓰지 않는다.
- 텍스트·`actions`·`background`는 모두 웹앱과 같은 마크다운(marked, GFM, 줄바꿈 = `<br>`)으로 렌더링된다.
  밑줄이 들어간 이름(`01_분말_포레스트`)은 `\_`로 이스케이프한다.

**숫자 표기(모든 텍스트 공통)**
- 금액: 만 원 단위로 반올림해 "약 3억 8,800만 원", "약 428,000원"(1만 원 미만은 원 단위). facts의 `*_krw`는 원.
- 비율: facts의 `*_pct` 값을 소수 1자리로("980.5%", "1,124.4%" — 천 단위 쉼표). 차이는 `%p`, 증감률은 `%`.
- CPC는 원 단위 정수("1,320원"), CTR·CVR은 소수 1~2자리.
- 날짜는 "10월 11일", 기간은 "10월 1일~11일". 요일·공휴일은 facts의 `weekday`·`holiday`.
- ROAS 목표는 facts `target.roas.target_pct`(이미 %로 변환됨)를 쓴다.

### 6. HTML 렌더링 & 전달

```bash
python3 "$ASSETS/build_report.py" render --work "$WORK" --texts "$WORK/texts.json" --out "<경로>"
```

- `<경로>`: 사용자가 지정한 경로. 없으면 `~/Downloads/laighthouse-reports/<brand>_<type>_<date>.html`
  (원격/샌드박스 환경이면 결과물 폴더의 같은 파일명).
- `render`는 이 보고서가 사용한 저장 응답 파일을 지운다(남은 파일은 24시간 후 자동 정리).
- 결과는 단독으로 열리는 HTML 한 파일이다(CSS·JS·차트 라이브러리 인라인, 폰트만 CDN). 파일을 사용자에게 전달한다.
- 완료 메시지는 짧게: 보고서 이름, 파일 위치, 가장 눈에 띄는 수치 한 가지.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `assets/build_report.py` | arm / plan / data(응답 수집 포함) / render. 웹앱 보고서 산식(정렬·반올림·표기 포함) |
| `assets/facts.py` | 텍스트 작성용 요약 수치(facts.json) |
| `assets/render_report.py` | 보고서 데이터 → 단일 HTML |
| `assets/report.js` | 웹앱 섹션 컴포넌트의 바닐라 JS 포팅(목표 카드, 차트 5종, 캘린더, 트리맵, 페이지/계층 표, 소진 표, AI 제안 패널·모달) |
| `assets/app.css` | 웹앱 스타일시트(수정 금지) |
| `assets/vendor/` | Chart.js 4.5.1, chartjs-plugin-datalabels 2.2.0, marked 15.0.12, ECharts 5.6.0(트리맵 전용 빌드) |
| `references/daily.md`·`mtd.md`·`monthly.md` | 섹션 구성·산식·텍스트/AI 제안 가이드 |
| `references/artifact-schema.md` | 보고서 데이터(JSON) 형식 |
| `../../hooks/save_mcp_response.py` | laighthouse MCP 응답 저장 훅(플러그인 공용, `arm`한 세션에서만 저장) |
