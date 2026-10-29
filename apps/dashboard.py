"""Read-only Streamlit front end; queries the API, not source platforms."""
import os

import chess
import chess.svg
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="chess4f · Chess intelligence", page_icon="♞", layout="wide")
API = os.environ.get("CHESS4F_API", "http://127.0.0.1:8000")


def get(path, params=None):
    try:
        r = httpx.get(API + path, params=params, timeout=60)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"API chưa sẵn sàng / dữ liệu chưa có: {exc}")
        return None


st.markdown("""<style>
.stApp{background:#f6f7fb}h1,h2,h3{color:#17213a}
[data-testid="stMetric"]{background:white;border:1px solid #dfe5f1;border-radius:12px;padding:18px}
</style>""", unsafe_allow_html=True)
st.title("♞ chess4f")
st.caption("Chess analytics • Delta Lake • Player intelligence • Delayed live observation")
section = st.sidebar.radio("Không gian phân tích", ["Tổng quan", "Hồ sơ cá nhân", "Ván đấu", "Dự đoán thử nghiệm", "Live observer", "Truy vết dữ liệu"])
st.sidebar.info("Dữ liệu hiển thị chỉ bao gồm phần đã nhập. Tần suất lịch sử không phải xác suất thắng hay gợi ý nước tốt nhất.")
if st.sidebar.button("Đọc lại dữ liệu"):
    st.rerun()

if section == "Tổng quan":
    source = st.selectbox("Nguồn phân tích",["lichess","chesscom","import"])
    data = get("/overview",{"source":source})
    if data:
        s = data["summary"]
        a,b,c = st.columns(3)
        a.metric("Ván đã nhập", f'{s["games"]:,}')
        b.metric("Nhận diện được", f'{s["recognized"]:,}')
        c.metric("Nhóm khai cuộc", s["opening_families"])
        st.caption(f'Phạm vi đã nhập: {s["first_game"]} → {s["last_game"]}')
        st.warning("Demo Lichess: 1.000 ván đầu khớp ngày 01/09/2026, không đại diện toàn ngày/tháng. Demo Chess.com: lịch sử một tài khoản, không đại diện toàn nền tảng. Hai nguồn được phân tích riêng.")
        st.info("Biểu đồ khai cuộc: chỉ Rated Blitz đã nhận diện. Mẫu số tỷ trọng gồm mọi nhóm đủ điều kiện, không chỉ Top N.")
        df = pd.DataFrame(data["openings"])
        if not df.empty:
            n = st.slider("Top nhóm", 5, 30, 10)
            fig = px.bar(df.head(n).iloc[::-1], x="popularity_pct", y="opening_family", orientation="h",
                         color_discrete_sequence=["#3155d9"], labels={"popularity_pct":"Tỷ trọng (%)", "opening_family":""})
            st.plotly_chart(fig, width="stretch")
            shown = df.head(n).melt(id_vars=["opening_family"], value_vars=["white_win_pct","draw_pct","black_win_pct"],var_name="Kết quả",value_name="Tỷ lệ (%)")
            st.plotly_chart(px.bar(shown,x="Tỷ lệ (%)",y="opening_family",color="Kết quả",orientation="h",barmode="stack"),width="stretch")
            st.dataframe(df, width="stretch")
        else:
            st.warning("Chưa có Rated Blitz đủ điều kiện. Hồ sơ cá nhân vẫn hỗ trợ các thể thức khác.")
elif section == "Hồ sơ cá nhân":
    source = st.selectbox("Nền tảng", ["chesscom", "lichess", "import"])
    username = st.text_input("Username", "hikaru")
    if username:
        data = get(f"/players/{source}/{username}")
        if data:
            s = data["summary"]
            for col, key, label in zip(st.columns(4), ["games","wins","draws","losses"], ["Số ván","Thắng","Hòa","Thua"]):
                col.metric(label, s.get(key) or 0)
            st.caption(data["coverage"])
            left, right = st.columns(2)
            left.subheader("Khai cuộc theo màu quân / thể thức")
            left.dataframe(data["openings"],width="stretch")
            right.subheader("Đối thủ gặp nhiều nhất")
            right.dataframe(data["opponents"],width="stretch")
            st.subheader("Lịch sử ván đã nhập")
            st.dataframe(data["history"],width="stretch")
elif section == "Ván đấu":
    game_key = st.text_input("Khóa ván: nền_tảng:ID")
    if game_key:
        data = get(f"/games/{game_key}")
        if data:
            game, moves = data["game"], data["moves"]
            ply = st.slider("Ply phát lại",0,len(moves),0) if moves else 0
            board = chess.Board(moves[ply-1]["fen_after"]) if ply else chess.Board()
            a,b = st.columns([1,1])
            with a:
                components.html(chess.svg.board(board,size=450),height=465)
            with b:
                st.write(f'{game["white"]} — {game["black"]}')
                st.write("Nhãn tại mốc:",moves[ply-1]["opening_name"] if ply else "Chưa có")
                st.caption("Giữ nhãn khớp sau cùng trong 36 ply đầu. Kết quả cuối ván không phải dự đoán.")
                player = game["white"] if board.turn else game["black"]
                result = get(f'/habits/{game["source"]}/{player}', {"fen":board.fen(),"before":game["played_at"],"exclude_game":game_key})
                if result:
                    st.write("Thói quen trước ván này:",player)
                    if result["insufficient_history"]:
                        st.warning("Dưới 20 quan sát hoặc chưa có lịch sử ở vị trí này.")
                    st.dataframe(result["moves"],width="stretch")
            with st.expander("Nguồn và phiên bản nhận diện"):
                st.json(game)
elif section == "Dự đoán thử nghiệm":
    report = get("/model")
    st.warning("Baseline trước ván chỉ dùng Elo. Chưa phải dự đoán theo vị trí, chưa hiệu chỉnh xác suất và không dùng để hỗ trợ khi thi đấu.")
    if report and report.get("model_id"):
        st.json(report)
        a,b = st.columns(2)
        white = a.number_input("Elo Trắng",report["rating_min"],report["rating_max"],int((report["rating_min"]+report["rating_max"])/2))
        black = b.number_input("Elo Đen",report["rating_min"],report["rating_max"],int((report["rating_min"]+report["rating_max"])/2))
        if st.button("Ước lượng thử"):
            result = get("/prediction",{"source":report["source"],"speed":report["speed"],"white_elo":white,"black_elo":black})
            if result:
                st.json(result)
    else:
        st.info("Chưa huấn luyện. CLI: chess4f train --source chesscom --speed blitz")
elif section == "Live observer":
    st.warning("Luồng công khai Lichess có độ trễ do nguồn. Dùng để quan sát; không phải công cụ hỗ trợ người đang thi đấu.")
    game_id = st.text_input("Lichess game ID (8 ký tự)")
    st.caption("Khởi động bộ nhận bằng: chess4f live GAME_ID. Trang này chỉ đọc trạng thái, không tự gửi nước đi.")
    if game_id:
        @st.fragment(run_every="3s")
        def live_panel():
            data = get(f"/live/{game_id}")
            if data:
                st.write("Trạng thái:",data["status"])
                st.caption(f'Nhận gần nhất: {data.get("received_at", "chưa có")} · {data["source_delay"]}')
                if data.get("fen"):
                    components.html(chess.svg.board(chess.Board(data["fen"]),size=440),height=455)
                st.write("Nhãn khớp gần nhất:",data.get("opening"))
                with st.expander("Sự kiện / trạng thái"):
                    st.json(data)
        live_panel()
else:
    st.subheader("Lịch sử pipeline")
    data = get("/runs")
    if data:
        st.dataframe([{k:v for k,v in r.items() if not isinstance(v,dict)} for r in data],width="stretch")
        with st.expander("Chi tiết và phiên bản Delta"):
            st.json(data)
