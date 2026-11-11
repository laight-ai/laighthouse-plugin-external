# 보고서 데이터 형식 (payload)

`build_report.py`가 만들고 `render_report.py`/`report.js`가 그리는 JSON. 웹앱의
`GET /api/analysis-artifact/{report_id}` 응답(`items`)과 같은 형식이라, 웹앱에서 받은 응답도 그대로 그릴 수 있다.

```json
{
  "meta": {
    "type": "daily | mtd | monthly",
    "name": "2026년 10월 11일 라형식품 일간 보고서",
    "reference_date": "2026-10-11 | 2026-10-01~2026-10-11 | 2026-09-01",
    "created": "2026-10-12 18:42", "author": "kjkim", "published": true,
    "brand": {"name": "라형식품", "advertiser": "Laight AI", "color": "rgb(63, 143, 115)", "initials": "라형"}
  },
  "items": [ {"order": 1, "analysis_artifact": {"type": "<type>", "data": {...}}}, ... ]
}
```

`order`가 없는 항목(`action_card`, `promotion`, `metadata`)은 본문 뒤로 간다. `promotion`·`metadata`는 그리지 않는다.
`action_card`는 daily·mtd에서 우측 AI 제안 패널에 표시된다.

| type | data 주요 필드 | 화면 |
|---|---|---|
| `target_progression` | `name`, `period{total,current}`, `items[{name, display, target, expected, actual, unit, change_rate}]` (ROAS는 배수) | 목표 카드(카드 없이 섹션 제목) |
| `text` | `slot_key`, `name`, `items: [markdown]` | 마크다운 카드 |
| `chart` | `slot_key`, `name`, `chart_series[{name,label,unit,items[{x,y}]}]` | 이름으로 프리셋 결정: `월별 광고 성과`(MTD 막대+ROAS, monthly는 월간형), `카테고리별 매출액 비교`, `일일 카테고리별 매출 현황` |
| `component_group` | `name`, `components[...]` | 그룹 안에서 `최근 7일 일별 광고 성과` 차트 = 일간 성과 차트+캘린더, 모두 `tree_map`이면 트리맵 묶음, `키워드/광고그룹/캠페인 성과` 표는 계층 표 하나로 합쳐짐 |
| `tree_map` | `cols`(campaign_name, ad_group_name, size, value, average, ratio), `units`, `items` (문자열) | 성과 진단 트리맵 |
| `paged_table` | `name`, `cols`, `items`(문자열 셀), `units`, `description` | 검색·정렬·페이지 표. 채널/캠페인/광고그룹 열이 있으면 계층 표 |
| `table` | `name`, `cols`, `items` | 단순 표 |
| `source_progression` | `items[{name:"그룹:매체", target, expected, actual}]` | 매체 예산 소진 표 |
| `daily_contribution` | `cols`, `dates`, `items` | 일자별 표 + 행 수 |
| `calendar` | `start_date`, `end_date`, `events[{name,type,start_date,end_date}]` | 프로모션 캘린더 |
| `action_card` | `title`, `tags`, `description`, `actions[]`, `background` | AI 제안 카드/상세 모달 |

셀 문자열은 화면에 그대로 표시된다(천 단위 쉼표·% 등 표기 포함). 숫자 열 판정·정렬은 렌더러가 한다.
