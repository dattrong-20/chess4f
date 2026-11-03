"""Player charts with explicit imported-history coverage."""
import pandas as pd
import plotly.express as px
import streamlit as st


def render(data):
    s = data["summary"]
    st.subheader(f'Hồ sơ · {data["player"]}')
    if not s["games"]:
        st.info("Chưa có ván của tài khoản này trong dữ liệu đã nhập. Tìm kiếm ở đây không tự tải lịch sử từ nền tảng. Bạn có thể thử Chess.com / hikaru với bộ demo hiện tại.")
        return
    for col, key, label in zip(st.columns(4), ["games", "wins", "draws", "losses"], ["Số ván", "Thắng", "Hòa", "Thua"]):
        col.metric(label, f'{int(s.get(key) or 0):,}', border=True)
    st.caption(f'Chỉ lịch sử đã nhập · {s["first_game"][:10]} → {s["last_game"][:10]} · Không khẳng định đầy đủ tài khoản')
    results = pd.DataFrame({"Kết quả": ["Thắng", "Hòa", "Thua"], "Số ván": [s["wins"], s["draws"], s["losses"]]})
    results["Tỷ lệ (%)"] = 100 * results["Số ván"] / s["games"]
    with st.container(border=True):
        st.subheader("Kết quả thực chiến")
        fig = px.bar(results, x="Kết quả", y="Tỷ lệ (%)", color="Kết quả", text_auto=".1f", hover_data=["Số ván"], color_discrete_map={"Thắng": "#247ba0", "Hòa": "#aab2bd", "Thua": "#ed9135"})
        fig.update_layout(height=300, showlegend=False, margin=dict(t=20,b=20))
        fig.update_yaxes(range=[0,100])
        st.plotly_chart(fig, width="stretch")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Khai cuộc thường sử dụng")
        openings = pd.DataFrame(data["openings"])
        if not openings.empty:
            openings["opening_family"] = openings.opening_family.fillna("Chưa nhận diện")
            ranked = openings.groupby("opening_family", as_index=False).games.sum().sort_values("games", ascending=False).head(10)
            fig = px.bar(ranked.iloc[::-1], x="games", y="opening_family", orientation="h", labels={"games":"Số ván", "opening_family":""})
            fig.update_layout(height=380, margin=dict(t=20,b=20))
            st.plotly_chart(fig, width="stretch")
        st.caption("Cộng số ván của mọi màu quân và thể thức trong lịch sử đã nhập.")
    with right, st.container(border=True):
        st.subheader("Đối thủ gặp nhiều nhất")
        opponents = pd.DataFrame(data["opponents"])
        if not opponents.empty:
            fig = px.bar(opponents.head(10).iloc[::-1], x="games", y="opponent", orientation="h", hover_data=["score_pct"], labels={"games":"Số ván", "opponent":"", "score_pct":"Điểm người chơi (%)"})
            fig.update_layout(height=380, margin=dict(t=20,b=20))
            st.plotly_chart(fig, width="stretch")
        st.caption("Chỉ tính các lần đối đầu đã có trong kho dữ liệu.")
    history = pd.DataFrame(data["history"])
    if not history.empty:
        st.subheader("Diễn biến Elo theo thể thức")
        speed = st.selectbox("Thể thức cho biểu đồ Elo", sorted(history.speed.dropna().unique()))
        trend = history[(history.speed == speed) & history.rating.notna()].copy()
        trend["played_at"] = pd.to_datetime(trend.played_at, utc=True)
        if not trend.empty:
            fig = px.line(trend.sort_values(["played_at", "game_key"]), x="played_at", y="rating", markers=True, labels={"played_at":"Thời điểm UTC", "rating":"Elo trước ván"}, hover_data=["opponent", "outcome"])
            fig.update_layout(height=320)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Chưa có Elo hợp lệ trong lựa chọn này.")
        st.caption(f'Biểu đồ và bảng lịch sử dùng {len(history)} ván gần nhất đã nhập (API giới hạn 200); các chỉ số và biểu đồ phía trên dùng toàn bộ {s["games"]} ván.')
        with st.expander("Lịch sử ván — lấy game_key để phát lại"):
            st.dataframe(history, hide_index=True, width="stretch")
            st.download_button("Tải lịch sử đang hiển thị", history.to_csv(index=False).encode("utf-8-sig"), file_name="player_history.csv", mime="text/csv")
    with st.expander("Bảng khai cuộc theo màu quân và thể thức"):
        st.dataframe(data["openings"], hide_index=True, width="stretch")
