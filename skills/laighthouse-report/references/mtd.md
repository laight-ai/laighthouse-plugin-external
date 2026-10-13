# MTD 보고서 (mtd)

웹앱 이름: `YY.MM.01 ~ YY.MM.DD {브랜드} MTD 보고서` · 머리글 `기준일 YYYY년 M월 D일 (요일) · 기간 YYYY-MM-01 ~ MM-DD`
레이아웃: 카드형 본문 + 우측 "AI 제안" 패널.

## 섹션 구성 (웹앱과 동일 순서)

| # | 섹션(slot_key) | 내용 | 데이터(plan key) · 산식 |
|---|---|---|---|
| 1 | 목표 달성 현황 | 목표 카드 + 진척률/소진율/달성률/누적 ROAS | `target` |
| 2 | Executive Summary (`mtd_executive_summary`) | **텍스트** | |
| 3 | 성과에 대한 개괄 (`mtd_performance_overview`) | **텍스트** | |
| 4 | 월별 광고 성과 (`ad_performance_recent_months`) | 최근 6개월 광고비·매출 막대 + ROAS 선 (당월은 MTD) | `months` (월 단위). 광고비 반올림, ROAS 서버값 소수 4자리 |
| 5 | 카테고리별 누적 판매액 (`items_table`) | 카테고리, 판매액, MoM(%) | `cat_month` (`day_offset`=경과일). MoM = 전월 **같은 일수** 대비, 판매액 내림차순 |
| 6 | 일일 카테고리별 매출 현황 (`daily_sales_by_category_chart`) | 상위 5개 카테고리 일별 매출 선 | `cat_day` |
| 7 | 제품 판매 성과의 심층 분석 (`mtd_ad_performance_analysis`) | **텍스트** | |
| 8 | 매체 별 예산 소진 현황 (`source_progression`) | 매체별 소진율 막대(진척률 표시선), 월 예산/예상 소진/실 소진/잔여 | `target_media.*` 월 예산, 예상 = round(예산×경과일/월일수), 실 소진 = floor(월초~기준일 광고비) |
| 9 | 캠페인 별 성과 (`campaign_table`) | 매체▸캠페인 계층 표 | `detail` 검색 매체(BRS/PLINK/NVSHOP), (캠페인, 매체) 합계. ROAS 내림차순 → 광고비 → 매출 → 이름 |
| 10 | 광고 그룹별 심층 분석 (`mtd_ad_group_analysis`) | **텍스트** | |
| 11 | 그룹 별 성과 (`groups_table`) | 광고그룹명 기준 합계 | 같은 정렬 |
| 12 | 키워드 별 성과 (`keywords_table`) | 키워드(ad_name, "-" 제외) 기준 합계 | 같은 정렬 |
| 13 | 일별 광고기여 매출 분석 (`daily_contribution`) | 일자별 광고비·클릭·구매·매출 | `daily_media` (광고비는 매체별 일값 반올림 후 합산) |

## 텍스트

모든 금액은 "약 3억 8,800만 원", "약 3,960만 원"처럼 만 원 단위 반올림, 비율은 소수 1자리, 차이는 %p.
비교 기준은 모두 **같은 일수(1일~기준일)** 끼리: 직전월 동기간·직전 3개월 평균·전년 동기.
월말 예상치는 모두 선형 증가 가정(기간 실적 ÷ 경과일 × 월일수)이며 facts의 `month_end_projection_krw`를 쓴다.
facts: `target`(목표·균등 배분·월말 예상·`projection_vs_target_krw`), `roas_comparison`, `same_period_by_month`,
`categories_same_period`(카테고리별 MoM·3개월·YoY·월말 예상), `daily_revenue_by_category`(요일 포함),
`category_daily_peaks`(카테고리별 일 매출 고점/저점·요일), `media_budget`,
`top_campaigns_by_impact`(전월 동기간 대비 매출 변화가 큰 매체-캠페인), `category_ad_response`(카테고리별 광고그룹 합산
광고비·매출·ROAS·CVR·CPC·클릭, 전월 동기간 대비), `top_ad_groups_by_revenue`(카테고리, 이번 기간 vs 전월 동기간 `changes`,
`roas_pct_same_period_by_month` 최근 3개월 동기간 ROAS), `promotions`(기간 중 프로모션).

### `mtd_executive_summary` (Executive Summary) — 불릿 4개, 각 불릿 최대 2문장
1. 첫 문장은 수치 없이 판정만 쓴다. 기간 ROAS vs 월 목표 ROAS(`target.roas.diff_pp`)에 따라
   "이번 달 ROAS는 목표 이상이었습니다." / "이번 달 ROAS는 목표에 근접한 수준입니다." /
   "이번 달 ROAS는 목표에 미치지 못했습니다." 중 하나. 이어서 기간 ROAS vs 목표(%p), 매출·예산의 균등 배분 대비
   초과/미달 금액, 현재 추이로 갔을 때 월말 예상 광고비·매출과 예산·목표 상회/미달 여부.
2. 이번 달 ROAS vs 직전월·직전 3개월 평균·전년 동기, 최근 13개월 중 위치와 추세.
3. 전체 성과에 가장 큰 영향을 미친 매체-캠페인 분석(`top_campaigns_by_impact`).
4. 매출 상위 카테고리(비중 %)와 성장/역성장 카테고리 분석.

### `mtd_performance_overview` (성과에 대한 개괄) — 소제목 3개 고정
```
### 1. 매출 발생 현황:
### 2. 예산 소진 현황:
### 3. ROAS 현황:
```
각 소제목 아래는 불릿이 아닌 한 문단. 1·2는 같은 구조(`target.revenue`/`target.cost`): 실제 값과 월 목표 대비 달성(소진)률 → 균등 배분 기준
(`even_pace_krw`) 대비 차이(`vs_even_pace_krw`) → 현재 추이 유지 시 월말 예상치(`month_end_projection_krw`)와
목표 대비 차이(`projection_vs_target_krw`). 3은 실제 ROAS vs 목표 ROAS와 그 의미, "최종 ROAS는 변동될 수 있음" 단서.

### `mtd_ad_performance_analysis` (제품 판매 성과의 심층 분석)
모든 불릿은 간결하게, **문장 2개 이하**.
```
# 카테고리별 광고 운영 및 매출 분석 (YYYY년 M월 1일~D일)
## Overview
- 기간 전체 매출과 카테고리 비중 …
- 최대 매출 카테고리의 최근 3개월 동기간 및 전년 동기 대비 성과 분석
- 두 번째 최대 매출 카테고리의 최근 3개월 동기간 및 전년 동기 대비 성과 분석
- 기타 카테고리 중 전월 대비 ROAS 변동 폭이 큰 카테고리에 대한 설명

## <최대 매출 카테고리명>
- 카테고리 매출 vs 직전월 동기간 대비 성과와 월말 예상 매출
- 해당 카테고리 광고그룹 1개의 전월 대비 효율 변화(ROAS, CVR, CPC, 클릭) — 가장 핵심적인 변화만, 관련 지표 최대 2개 인용
- 일별 매출 고점/저점과 요일

## <두 번째 최대 매출 카테고리명>
- (위와 같은 3개 불릿)
```
- 카테고리별 섹션은 매출 상위 2개 카테고리만 쓴다.
- 기타 카테고리의 ROAS 변동은 `category_ad_response[].changes.roas_diff_pp`(상위 2개 제외)에서 절대값이 큰 것.
- 월말 예상 매출은 `categories_same_period[].month_end_projection_krw`, 고점/저점은 `category_daily_peaks`.
- 카테고리↔광고그룹 연결은 `top_ad_groups_by_revenue[].category`를 쓴다(`ctx_cat_groups` 응답 기준).

### `mtd_ad_group_analysis` (광고 그룹별 심층 분석)
```
• 유의미한 수준의 매출이 발생하면서도, 세부 사항을 점검했을 때에 매출 개선 효과가 클 것으로 예상되는 광고그룹 3개를 선정하였습니다.

• 쇼핑검색 01\_믹스\_노바커피 (커피)
  • ROAS/전환율/CTR의 전월 대비 변화와 원인 추정
  • ROAS 최근 3개월 변화 추이 및 평가
```
선정: `top_ad_groups_by_revenue`(매출 상위 20개) 중 매출 규모가 크면서 `changes`의 악화/개선 폭
(CVR %p, ROAS %p, CPC %)이 큰 **3개**. 괄호 안은 `category`, 매체명은 `media`. 광고그룹명의 `_`는 `\_`로 쓴다.
3개월 추이는 `roas_pct_same_period_by_month`(각 월 1일~기준일 동기간 ROAS %).

## AI 제안 (action_cards) — 보통 4개, `description`은 빈 문자열("")

| title 예 | tags | 내용 |
|---|---|---|
| `캠페인 일광고비 조정 제안` | `["예산"]` | 어떤 캠페인의 예산을 조정해야 하는지만 제안. 구체적인 조정 범위는 언급하지 않는다 |
| `광고 그룹 수준 개선안: 랜딩 페이지 개선 및 소재 점검` | `["소재"]` | |
| `프로모션 운영 개선안: 카테고리별 운영 최적화` | `["프로모션"]` | `promotions`·`categories_same_period` 근거 |
| `광고 채널 수준 예산 조정: <채널> 채널의 …에 따른 예산 조정` | `["예산"]` | `media_budget` 근거 |

- `actions`는 실행 문장 1~4개. 예산 조정은 방향성(증액/유지/감액)만 제시하고 구체적인 금액 조정 범위는 쓰지 않는다.
- `background`는 `● ` 또는 `- `로 시작하는 근거 문단 2~3개.
- `actions`와 `background`의 각 항목은 간결한 문체로, 가장 핵심적인 근거·데이터 1개만 언급해 **문장 1개**로 쓴다.
