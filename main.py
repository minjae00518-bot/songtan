import re
from collections import Counter
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="급식 규칙 찾기", layout="wide")


# 데이터 로드 및 연관 규칙 계산 함수
@st.cache_data
def load_and_process_data():
  url = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"
  df = pd.read_csv(url, encoding="utf-8")

  transactions = []
  all_items = set()

  # 식단별 메뉴 정제 및 트랜잭션 구성
  for menu_str in df["메뉴"].dropna():
    if not isinstance(menu_str, str):
      continue

    # 괄호 및 괄호 안 내용 제거 후 공백 정리
    items = []
    for item in menu_str.split("|"):
      cleaned = re.sub(r"\(.*?\)", "", item).strip()
      if cleaned:
        items.append(cleaned)

    # 중복 제거 및 정렬
    unique_items = sorted(list(set(items)))
    if unique_items:
      transactions.append(unique_items)
      all_items.update(unique_items)

  total_days = len(transactions)  # 총 급식 일수

  # 개별 메뉴 출현 빈도
  item_counts = Counter()
  for t in transactions:
    for item in t:
      item_counts[item] += 1

  # 함께 출현한 메뉴 쌍 빈도 (정렬된 튜플을 키로 사용)
  pair_counts = Counter()
  for t in transactions:
    for a, b in combinations(t, 2):
      pair_counts[tuple(sorted([a, b]))] += 1

  # 연관 규칙 생성 (A -> B 및 B -> A)
  rules = []
  unique_pairs = set()

  for (a, b), co_cnt in pair_counts.items():
    if co_cnt > 0:
      unique_pairs.add((a, b))

      # 지지도, 신뢰도, 향상도 계산
      sup = co_cnt / total_days
      conf_ab = co_cnt / item_counts[a]
      conf_ba = co_cnt / item_counts[b]

      lift = (co_cnt * total_days) / (item_counts[a] * item_counts[b])

      # 규칙 1: A -> B
      rules.append({
          "조건": a,
          "결과": b,
          "동시": co_cnt,
          "지지도": round(sup, 4),
          "신뢰도": round(conf_ab, 4),
          "향상도": round(lift, 4),
      })
      # 규칙 2: B -> A
      rules.append({
          "조건": b,
          "결과": a,
          "동시": co_cnt,
          "지지도": round(sup, 4),
          "신뢰도": round(conf_ba, 4),
          "향상도": round(lift, 4),
      })

  rules_df = pd.DataFrame(rules)
  sorted_items = sorted(list(all_items))

  return (
      total_days,
      len(sorted_items),
      len(unique_pairs),
      sorted_items,
      rules_df,
      item_counts,
      pair_counts,
  )


# 메인 화면 구성
st.title("🍱 급식 규칙 찾기")
st.markdown(
    "송탄고등학교 184일간의 급식 데이터를 분석하여 함께 자주 나오는 메뉴 연관 규칙을"
    " 시각화합니다."
)

# 데이터 불러오기
(
    total_days,
    total_items,
    total_pairs,
    item_list,
    rules_df,
    item_counts,
    pair_counts,
) = load_and_process_data()

# 요약 정보 표시 (한 줄 배치)
col1, col2, col3 = st.columns(3)
col1.metric("급식 일수", f"{total_days}일")
col2.metric("메뉴 종류 수", f"{total_items}개")
col3.metric("함께 나온 적이 있는 메뉴 쌍의 수", f"{total_pairs}개")

st.divider()

# 검색 및 정렬 필터 영역 (3컬럼)
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)

with ctrl_col1:
  selected_menu = st.selectbox(
      "메뉴 선택 (특정 메뉴가 포함된 규칙 모아보기)",
      options=["전체"] + item_list,
  )

with ctrl_col2:
  min_co_days = st.slider(
      "최소 동시 일수 선택", min_value=1, max_value=10, value=1
  )

with ctrl_col3:
  sort_option = st.selectbox(
      "정렬 기준 선택", options=["향상도 순", "신뢰도 순", "동시 순"]
  )

# 정렬 컬럼 매핑
sort_map = {"향상도 순": "향상도", "신뢰도 순": "신뢰도", "동시 순": "동시"}
sort_col = sort_map[sort_option]

# 조건 1: 특정 메뉴 필터링
if selected_menu == "전체":
  filtered_df = rules_df.copy()
else:
  filtered_df = rules_df[
      (rules_df["조건"] == selected_menu) | (rules_df["결과"] == selected_menu)
  ].copy()

# 조건 2: 최소 동시 일수 필터링
filtered_df = filtered_df[filtered_df["동시"] >= min_co_days]

# 조건 3: 정렬 적용
filtered_df = filtered_df.sort_values(
    by=[sort_col, "동시"], ascending=[False, False]
).reset_index(drop=True)

# 남은 규칙 개수 한 줄 안내
st.info(f"🔍 조건에 부합하여 표에 남은 규칙 수: **{len(filtered_df)}**개")

# 시각화 영역: 향상도 상위 10개 가로 막대그래프
st.subheader("📊 향상도 상위 10개 규칙")

if not filtered_df.empty:
  # 필터링된 데이터 중 향상도 기준 상위 10개 추출
  top10_df = filtered_df.sort_values(by="향상도", ascending=False).head(10)
  top10_df["규칙"] = top10_df["조건"] + " → " + top10_df["결과"]

  # 차트 y축 위쪽에 높은 값이 오도록 오름차순 정렬
  top10_df_chart = top10_df.sort_values(by="향상도", ascending=True)

  fig = px.bar(
      top10_df_chart,
      x="향상도",
      y="규칙",
      orientation="h",
      text="향상도",
      color="향상도",
      color_continuous_scale="Viridis",
      title=(
          f"[{selected_menu}] 관련 향상도 Top 10 (최소 동시 {min_co_days}일 이상)"
          if selected_menu != "전체"
          else f"전체 메뉴 향상도 Top 10 (최소 동시 {min_co_days}일 이상)"
      ),
  )

  fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
  fig.update_layout(
      xaxis_title="향상도 (Lift)",
      yaxis_title="연관 규칙 (조건 → 결과)",
      height=400,
      showlegend=False,
  )

  st.plotly_chart(fig, use_container_width=True)
else:
  st.warning("선택한 조건에 해당하는 규칙이 없습니다.")

# 표 출력 영역
st.subheader("📋 연관 규칙 결과 표")
st.dataframe(
    filtered_df,
    column_config={
        "지지도": st.column_config.NumberColumn(format="%.4f"),
        "신뢰도": st.column_config.NumberColumn(format="%.4f"),
        "향상도": st.column_config.NumberColumn(format="%.4f"),
    },
    use_container_width=True,
    hide_index=True,
)

# 표 아래: 함께 나온 적 없는 짝 화면 영역
st.divider()
st.subheader("🚫 함께 나온 적 없는 짝")
st.caption(
    "선택한 메뉴와 한 번도 함께 나오지 않았으며, 단독으로는 10일 이상 나온 메뉴를"
    " 조회합니다."
)

unpaired_selected_menu = st.selectbox(
    "짝을 확인할 대상 메뉴 선택", options=item_list, key="unpaired_menu_select"
)

# 선택된 메뉴의 전체 제공 일수
selected_days_count = item_counts[unpaired_selected_menu]
st.markdown(
    f"📌 **[{unpaired_selected_menu}]** 메뉴가 전체 급식에 등장한 총 횟수: **{selected_days_count}일**"
)

# 함께 나온 적 없는 (동시=0) & 혼자서는 10일 이상 나온 메뉴 탐색
never_paired_list = []
for target in item_list:
  if target == unpaired_selected_menu:
    continue

  pair_key = tuple(sorted([unpaired_selected_menu, target]))
  co_occurrence = pair_counts.get(pair_key, 0)
  target_days_count = item_counts[target]

  if co_occurrence == 0 and target_days_count >= 10:
    never_paired_list.append(
        {"함께 나오지 않은 메뉴": target, "해당 메뉴 단독 제공 일수": target_days_count}
    )

never_paired_df = pd.DataFrame(never_paired_list)

if not never_paired_df.empty:
  never_paired_df = never_paired_df.sort_values(
      by="해당 메뉴 단독 제공 일수", ascending=False
  ).reset_index(drop=True)

  st.dataframe(never_paired_df, use_container_width=True, hide_index=True)
else:
  st.write(
      "해당 메뉴와 동시 제공 횟수가 0회이면서, 10일 이상 제공된 다른 메뉴가"
      " 없습니다."
  )
