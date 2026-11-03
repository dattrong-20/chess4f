"""Opening charts over a pinned, aggregated Trino release."""
import pandas as pd
import plotly.express as px
import streamlit as st

from theme import COLORS, WDL, style


def render(payload):
    st.header("Khai cuộc · mức sử dụng và kết quả")
    st.info("Tỷ lệ điểm Trắng = (số ván Trắng thắng + 0,5 × số ván hòa) / tổng số ván × 100%. Đây là kết quả thực chiến, không phải xác suất thắng của một thế cờ hay tác động nhân quả của khai cuộc.")
    df = pd.DataFrame(payload["rows"])
    if df.empty:
        st.warning("Chưa có ván đủ điều kiện cho nguồn này.")
        return
    months = sorted(df.year_month.unique())
    groups = [g for g in ["<1200", "1200–1599", "1600–1999", "≥2000", "unknown"] if g in df.rating_group.unique()]
    left, right = st.columns(2)
    chosen_months = left.multiselect("Tháng có dữ liệu", months, default=months)
    chosen_groups = right.multiselect("Nhóm Elo trung bình hai bên", groups, default=groups)
    minimum = st.number_input("Số ván tối thiểu để so sánh kết quả", 1, 5000, 50, 10)
    df = df[df.year_month.isin(chosen_months) & df.rating_group.isin(chosen_groups)]
    if df.empty:
        st.warning("Không có dữ liệu trong bộ lọc đã chọn.")
        return
    values = ["n_games", "white_wins", "draws", "black_wins"]

    def aggregate(keys, frame=df):
        result = frame.groupby(keys, as_index=False)[values].sum()
        result["score_pct"] = 100 * (result.white_wins + .5 * result.draws) / result.n_games
        return result

    totals = aggregate(["opening_family"]).sort_values("n_games", ascending=False)
    totals["popularity_pct"] = 100 * totals.n_games / totals.n_games.sum()
    n = st.slider("Số nhóm phổ biến hiển thị", 5, 20, 10)
    top = totals.head(n).opening_family.tolist()
    st.metric("Ván đủ điều kiện sau lọc", f'{int(totals.n_games.sum()):,}', border=True)
    view = st.selectbox("Câu hỏi phân tích", ["C1 · Phổ biến", "C2 · Xu hướng sử dụng", "C3 · Thắng, hòa, thua", "C4 · Kết quả theo Elo", "C5 · Phổ biến và kết quả", "C6 · So sánh biến thể", "C7 · Kết quả theo tháng"])
    fig = None
    table = totals
    if view.startswith("C1"):
        table = totals.head(n)
        fig = px.bar(table.iloc[::-1], x="popularity_pct", y="opening_family", orientation="h", labels={"popularity_pct": "Tỷ trọng (%)", "opening_family": "Nhóm khai cuộc"}, text_auto=".2f")
    elif view.startswith("C2"):
        table = aggregate(["year_month", "opening_family"])
        table["popularity_pct"] = 100 * table.n_games / table.groupby("year_month").n_games.transform("sum")
        table = table[table.opening_family.isin(top[:5])]
        fig = px.line(table, x="year_month", y="popularity_pct", color="opening_family", markers=True, labels={"year_month": "Tháng", "popularity_pct": "Tỷ trọng (%)"})
        st.caption("Chỉ hiển thị tháng/nhóm có quan sát; tháng không có dữ liệu không được thay bằng 0.")
    elif view.startswith("C4"):
        table = aggregate(["opening_family", "rating_group"])
        table = table[table.opening_family.isin(top) & (table.n_games >= minimum)]
        if not table.empty:
            matrix = table.pivot(index="opening_family", columns="rating_group", values="score_pct").reindex(index=top, columns=chosen_groups)
            matrix.index.name = "Nhóm khai cuộc"
            matrix.columns.name = "Nhóm Elo"
            fig = px.imshow(matrix, text_auto=".1f", zmin=40, zmax=60, color_continuous_scale="RdBu", color_continuous_midpoint=50, labels={"color": "Điểm Trắng (%)"}, aspect="auto")
        st.caption("Thang màu 40–60%. Ô trống là không có quan sát hoặc chưa đủ mẫu; không phải điểm bằng 0%.")
    elif view.startswith("C5"):
        table = totals[totals.n_games >= minimum]
        fig = px.scatter(table, x="popularity_pct", y="score_pct", hover_name="opening_family", size="n_games", size_max=35, labels={"popularity_pct": "Tỷ trọng (%)", "score_pct": "Điểm Trắng (%)"})
        fig.add_hline(y=50, line_dash="dot")
    elif view.startswith("C7"):
        group = st.selectbox("Nhóm Elo so sánh", chosen_groups)
        table = aggregate(["year_month", "opening_family"], df[df.rating_group == group])
        table = table[table.opening_family.isin(top[:5])].copy()
        table.loc[table.n_games < minimum, "score_pct"] = float("nan")
        fig = px.line(table, x="year_month", y="score_pct", color="opening_family", markers=True, hover_data=["n_games"], labels={"score_pct": "Điểm Trắng (%)", "year_month": "Tháng"})
        fig.update_yaxes(range=[0, 100])
        st.caption("Các điểm dưới ngưỡng được để trống. Hai tháng chỉ đủ minh họa so sánh, chưa chứng minh xu hướng dài hạn.")
    else:
        key = "opening_family"
        table = totals[totals.opening_family.isin(top) & (totals.n_games >= minimum)]
        if view.startswith("C6"):
            family = st.selectbox("Nhóm khai cuộc", totals.opening_family.tolist())
            group = st.selectbox("Nhóm Elo so sánh", chosen_groups)
            key = "opening_name"
            table = aggregate([key], df[(df.opening_family == family) & (df.rating_group == group)])
            table = table[table.n_games >= minimum].sort_values("n_games", ascending=False).head(12)
        melted = table.melt(id_vars=[key, "n_games"], value_vars=["white_wins", "draws", "black_wins"], var_name="Kết quả", value_name="count")
        melted["Tỷ lệ (%)"] = 100 * melted["count"] / melted.n_games
        melted["Kết quả"] = melted["Kết quả"].map({"white_wins": "Trắng thắng", "draws": "Hòa", "black_wins": "Đen thắng"})
        fig = px.bar(melted, x="Tỷ lệ (%)", y=key, color="Kết quả", orientation="h", barmode="stack",
                     color_discrete_map=WDL)
        fig.update_xaxes(range=[0, 100])
    if table.empty:
        st.warning("Chưa đủ mẫu cho lựa chọn này. Hãy mở rộng bộ lọc hoặc điều chỉnh ngưỡng; ngưỡng thấp làm kết quả kém ổn định.")
    elif fig is not None:
        style(fig, height=520)
        if view.startswith(("C2", "C7")):
            fig.update_xaxes(type="category")
        st.plotly_chart(fig, width="stretch")
    with st.expander("Bảng số liệu và tải xuống"):
        st.dataframe(table, hide_index=True)
        st.download_button("Tải bảng CSV", table.to_csv(index=False).encode("utf-8-sig"), file_name=f'{view[:2]}_openings.csv', mime="text/csv")
