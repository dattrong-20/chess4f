"""Player charts with explicit imported-history coverage."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from theme import COLORS, WDL_SHORT, style, thousands


def render(data):
    s = data["summary"]
    st.subheader(f'Hồ sơ · {data["player"]}')
    if not s["games"]:
        st.info("Chưa có ván của tài khoản này trong dữ liệu đã nhập. Mở mục Tải / cập nhật lịch sử ở phía trên để đồng bộ tài khoản, hoặc thử Chess.com / hikaru với bộ demo hiện tại.")
        return
    for col, key, label in zip(st.columns(4), ["games", "wins", "draws", "losses"], ["Số ván", "Thắng", "Hòa", "Thua"]):
        col.metric(label, thousands(int(s.get(key) or 0)), border=True)
    wins, draws, losses = int(s.get("wins") or 0), int(s.get("draws") or 0), int(s.get("losses") or 0)
    with st.container(border=True):
        st.subheader("Kết quả thực chiến")
        donut = go.Figure(go.Pie(
            labels=["Thắng", "Hòa", "Thua"], values=[wins, draws, losses], hole=0.55, sort=False,
            marker=dict(colors=[WDL_SHORT["Thắng"], WDL_SHORT["Hòa"], WDL_SHORT["Thua"]]),
            textinfo="percent", textfont=dict(size=14),
            hovertemplate="%{label}: %{value:,} ván (%{percent})<extra></extra>"))
        donut.add_annotation(text=f"{thousands(s['games'])} ván", showarrow=False, font=dict(size=20, color="#0f172a"))
        style(donut, height=300, legend=dict(orientation="h", y=-0.08, x=0))
        st.plotly_chart(donut, width="stretch")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Khai cuộc thường sử dụng")
        openings = pd.DataFrame(data["openings"])
        if not openings.empty:
            openings["opening_family"] = openings.opening_family.fillna("Chưa nhận diện")
            ranked = openings.groupby("opening_family", as_index=False).games.sum().sort_values("games", ascending=False).head(10)
            fig = px.bar(ranked.iloc[::-1], x="games", y="opening_family", orientation="h",
                         color_discrete_sequence=[COLORS["primary"]],
                         labels={"games":"Số ván", "opening_family":""}, text_auto=",d")
            style(fig, height=380)
            st.plotly_chart(fig, width="stretch")
        st.caption("Cộng số ván của mọi màu quân và thể thức trong lịch sử đã nhập.")
    with right, st.container(border=True):
        st.subheader("Đối thủ gặp nhiều nhất")
        opponents = pd.DataFrame(data["opponents"])
        if not opponents.empty:
            fig = px.bar(opponents.head(10).iloc[::-1], x="games", y="opponent", orientation="h",
                         color_discrete_sequence=[COLORS["accent"]],
                         hover_data=["score_pct"], labels={"games":"Số ván", "opponent":"", "score_pct":"Điểm người chơi (%)"})
            style(fig, height=380)
            st.plotly_chart(fig, width="stretch")
        st.caption("Chỉ tính các lần đối đầu đã có trong kho dữ liệu.")
    history = pd.DataFrame(data["history"])
    if not history.empty:
        st.subheader("Diễn biến Elo theo thể thức")
        speed = st.selectbox("Thể thức cho biểu đồ Elo", sorted(history.speed.dropna().unique()))
        trend = history[(history.speed == speed) & history.rating.notna()].copy()
        trend["played_at"] = pd.to_datetime(trend.played_at, utc=True)
        if not trend.empty:
            fig = px.line(trend.sort_values(["played_at", "game_key"]), x="played_at", y="rating", markers=True,
                          color_discrete_sequence=[COLORS["primary"]],
                          labels={"played_at":"Thời điểm UTC", "rating":"Elo trước ván"},
                          hover_data=["opponent", "outcome"])
            style(fig, height=320)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Chưa có Elo hợp lệ trong lựa chọn này.")
        with st.expander("Lịch sử ván — lấy game_key để phát lại"):
            st.dataframe(history, hide_index=True, width="stretch")
            st.download_button("Tải lịch sử đang hiển thị", history.to_csv(index=False).encode("utf-8-sig"), file_name="player_history.csv", mime="text/csv")
    with st.expander("Bảng khai cuộc theo màu quân và thể thức"):
        st.dataframe(data["openings"], hide_index=True, width="stretch")
