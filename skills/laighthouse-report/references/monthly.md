# 월 마감 보고서 (monthly)

웹앱 이름: `YYYY년 M월 {브랜드} 월 마감 보고서`
레이아웃: 회색 배경 위 A4형 종이(`sheet`) — 표지(브랜드 타일·"Monthly Performance Report"·제목·
`YYYY년 M월 1일 – M월 말일 · 전월(YYYY년 M월) 대비`), 번호가 붙은 섹션(01, 02 …), 하단 바닥글.
AI 제안 패널 없음.

## 섹션 구성 (웹앱과 동일 순서)

| # | 섹션(slot_key) | 내용 | 데이터(plan key) · 산식 |
|---|---|---|---|
| 01 | 목표 달성 현황 | 목표 카드 + 소진율/달성률/누적 ROAS 요약(종이형 카드) | `target` (as_of=말일), 기간 = 월일수/월일수 |
| 02 | 월별 광고 성과 (`ad_performance_recent_months`) | 최근 6개월 광고비·매출 막대 + ROAS 선 | `months`(13개월 조회, 차트는 최근 6개월). 광고비 반올림, ROAS 서버값 소수 4자리 |
| 03 | Executive Summary (`monthly_executive_summary`) | **텍스트** | |
| 04 | 카테고리별 매출액 비교 (`monthly_sales_by_category_chart`) | 카테고리별 전월 vs 당월 막대 + 증감률 라벨 | `cat_month`, 당월 매출 내림차순, 전체 카테고리 |
| 05 | 일일 카테고리별 매출 현황 (`monthly_daily_sales_by_category_chart`) | 상위 5개 카테고리 일별 매출 선 | `cat_day` |
| 06 | 제품 판매 트렌드 분석 (`monthly_sales_trend_analysis`) | **텍스트** | |
| 07 | 매체 별 성과 비교 (`monthly_source_progression_group`) | 매체별 표(월, 광고비 (원), 매출 (원), ROAS) 전월·당월 | `media_month`. 광고비·매출 버림(정수), ROAS 서버값 소수 2자리 + % |

## 텍스트

### `monthly_executive_summary` (Executive Summary)
```
• <월> 퍼포먼스 마케팅 성과는 좋았습니다/아쉬웠습니다. 광고비 목표 대비 집행, 매출 목표 달성 여부, ROAS vs 목표(%p), 최근 13개월 중 위치.
  - 핵심 관찰 1 (역성장/성장 카테고리, 원인 신호)
  - 핵심 관찰 2

• 권장 사항
  - 다음 달 전체 광고 예산 조정 범위(현재 약 OOO만 원 → 범위)와 근거, 담당자 협의 권고
  - 카테고리/상품 측면 권고(프로모션·상품 구성 등)
```
근거: facts `target`(목표 대비), `months`(13개월)·`roas_rank_in_listed_months`(13개월 중 ROAS 순위),
`revenue_mom_chg_pct`/`revenue_yoy_chg_pct`, `categories`(전월·전년 동월 대비, 6개월 추이),
`top_ad_groups_by_revenue`(카테고리, 당월 vs 전월 `changes`).

### `monthly_sales_trend_analysis` (제품 판매 트렌드 분석)
`◆ `로 시작하는 문단 4~5개(문단 사이 빈 줄):
1. 전체 매출 vs 전월·전년 동월, 성장/역성장 카테고리 정리.
2~5. 카테고리별 관찰 — 광고비 증감 대비 매출 반응(해당 카테고리 광고그룹의 클릭·전환율),
   월중 급변 시점·월 후반 추세(`category_daily`: 상·하반월 일평균, 최고/최저일). 원인을 데이터로 특정할 수
   없으면 그렇게 쓴다.
