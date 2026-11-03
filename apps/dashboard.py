"""Streamlit front end: Trino-backed analytics and queued ingestion via API."""
import hmac
import os
import re

import chess
import chess.svg
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="chess4f · Chess intelligence", page_icon="♞", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 1200px;}
  [data-testid="stMetric"] {background: #262421; border: 1px solid #3D3A37; border-radius: 12px; padding: 14px 16px;}
  [data-testid="stMetricValue"] {font-weight: 700; color: #E8E6E3;}
  [data-testid="stSidebar"] {border-right: 1px solid #3D3A37;}
  [data-testid="stHeader"] {background: transparent;}
  h1, h2, h3 {letter-spacing: -0.01em; color: #E8E6E3;}
  .stButton > button[kind="primary"] {background: #81B64C; border-color: #81B64C; color: #1F1F1C;}
  /* Keep the sidebar collapse/expand control: only hide the deploy button. */
  [data-testid="stAppDeployButton"], [data-testid="stDecoration"] {display: none;}
  [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"] {visibility: visible !important;}
</style>
""", unsafe_allow_html=True)
API = os.environ.get("CHESS4F_API", "http://127.0.0.1:8000")
DASHBOARD_PASSWORD = os.environ.get("CHESS4F_DASHBOARD_PASSWORD")

if DASHBOARD_PASSWORD and not st.session_state.get("dashboard_authenticated"):
    st.title("chess4f")
    st.caption("Khu vực phân tích nội bộ")
    with st.form("dashboard-login"):
        password = st.text_input("Mật khẩu", type="password")
        submitted = st.form_submit_button("Đăng nhập", type="primary")
    if submitted:
        if hmac.compare_digest(password, DASHBOARD_PASSWORD):
            st.session_state["dashboard_authenticated"] = True
            st.rerun()
        else:
            st.error("Sai mật khẩu")
    st.stop()


def get(path, params=None):
    try:
        r = httpx.get(API + path, params=params, timeout=60)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"API chưa sẵn sàng / dữ liệu chưa có: {exc}")
        return None


def fetch_game(key):
    """Fetch one game once; a 404 is not an error worth interrupting the UI."""
    try:
        response = httpx.get(API + f"/games/{key}", timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


def game_key_from_input(value):
    text = value.strip()
    if ":" in text:
        return text
    match = re.search(r"chess\.com/game/(?:live|daily)/(\d+)", text)
    if match:
        return f"chesscom:{match.group(1)}"
    match = re.search(r"lichess\.org/(?:game/)?([A-Za-z0-9]{8})", text)
    if match:
        return f"lichess:{match.group(1)}"
    if text.isdigit():
        return f"chesscom:{text}"
    return f"lichess:{text}"


@st.fragment
def replay_board(data, key):
    """Board, arrows and move list; button clicks rerun only this fragment."""
    game, moves = data["game"], data["moves"]
    max_ply = len(moves)
    if st.session_state.get("replay_key") != key:
        st.session_state["replay_key"] = key
        st.session_state["replay_ply"] = 0
    ply = int(st.session_state.get("replay_ply", 0))
    board = chess.Board(moves[ply-1]["fen_after"]) if ply else chess.Board()
    left, right = st.columns([1, 1])
    with left:
        st.image(chess.svg.board(board, size=450, colors=BOARD_COLORS), width=450)
        prev_col, info_col, next_col = st.columns([1, 2, 1])
        if prev_col.button("◀", disabled=ply <= 0, key="ply_prev"):
            st.session_state["replay_ply"] = max(0, ply - 1)
            st.rerun(scope="fragment")
        if next_col.button("▶", disabled=ply >= max_ply, key="ply_next"):
            st.session_state["replay_ply"] = min(max_ply, ply + 1)
            st.rerun(scope="fragment")
        info_col.markdown(
            f"<div style='text-align:center;padding-top:0.45rem'>Ply {ply} / {max_ply}</div>",
            unsafe_allow_html=True)
    with right:
        st.write(f'{game["white"]} — {game["black"]}')
        table = pd.DataFrame([
            {"Ply": move["ply"], "Màu": "Trắng" if move["ply"] % 2 else "Đen",
             "Mã nước": move["uci"], "SAN": move["san"],
             "▶": "▶" if move["ply"] == ply else ""}
            for move in moves
        ])
        st.dataframe(table, height=400, hide_index=True, width="stretch")


SOURCE_NAMES = {"lichess": "Lichess", "chesscom": "Chess.com", "import": "PGN nhập thủ công"}
SPEEDS = ["blitz", "rapid", "bullet", "classical", "all"]
SPEED_NAMES = {"blitz": "Blitz", "rapid": "Cờ 10 phút (Rapid)", "bullet": "Bullet",
               "classical": "Classical", "all": "Tất cả thể thức"}
BOARD_COLORS = {"square light": "#EEEED2", "square dark": "#769656"}
st.title("chess4f")
st.caption("Khám phá khai cuộc · Hiểu lịch sử thi đấu · Theo dõi dữ liệu")
st.sidebar.title("chess4f")
st.sidebar.caption("CHESS ANALYTICS WORKSPACE")
section = st.sidebar.radio("Không gian phân tích", ["Tổng quan", "Khai cuộc C1–C7", "Hồ sơ cá nhân", "Ván đấu", "Live observer", "Nhập dữ liệu"])
if st.sidebar.button("Đọc lại dữ liệu"):
    st.rerun()

if section == "Tổng quan":
    st.subheader("Tổng quan nguồn dữ liệu")
    a, b = st.columns(2)
    source = a.selectbox("Nguồn phân tích",["lichess","chesscom","import"], format_func=SOURCE_NAMES.get)
    speed = b.selectbox("Thể thức", SPEEDS, format_func=SPEED_NAMES.get, index=0)
    data = get("/overview",{"source":source,"speed":speed})
    if data:
        s = data["summary"]
        if not s["games"]:
            with st.container(border=True):
                st.subheader("Chưa có dữ liệu từ nguồn này", icon=":material/folder_open:")
                st.write("PGN nhập thủ công là nhóm riêng cho các tệp được nhập với nhãn import; không phải tổng dữ liệu Lichess và Chess.com." if source == "import" else "Nguồn này chưa có ván trong bản dữ liệu đã công bố.")
                st.caption("Chọn Lichess hoặc Chess.com để xem dữ liệu hiện có. Việc đổi nguồn không xóa dữ liệu.")
            st.stop()
        a,b,c = st.columns(3)
        a.metric("Ván đã nhập", f'{s["games"]:,}', border=True)
        b.metric("Nhận diện được", f'{s["recognized"]:,}', border=True)
        c.metric("Nhóm khai cuộc", s["opening_families"], border=True)
        st.caption(f'Phạm vi đã nhập: {s["first_game"]} → {s["last_game"]}')
        with st.expander("Phạm vi mẫu và cách cập nhật", expanded=False):
            if source == "lichess":
                st.write("Mỗi lượt thu thập demo giới hạn 1.000 ván Rated Blitz đầu tiên khớp tháng. Bộ mẫu ban đầu tháng 9 và tháng 10/2026 gồm 2.000 ván; đồng bộ người chơi và ván trực tiếp có thể bổ sung dữ liệu; đây không phải giới hạn lưu trữ của hệ thống.")
                st.write("Chạy lại cùng nguồn và giới hạn sẽ không cộng thêm ván trùng. Muốn mở rộng cần tăng giới hạn hoặc nhập thêm tháng, sau đó kiểm chứng và công bố bản mới.")
            elif source == "chesscom":
                st.write("Bộ demo ban đầu gồm lịch sử Hikaru tháng 9/2026; lịch sử đồng bộ thêm được gộp theo ID ván duy nhất. Số ván phản ánh dữ liệu đã nhập, không đại diện toàn nền tảng.")
            else:
                st.write("Nguồn PGN nhập thủ công, được phân tích riêng với hai nền tảng.")
        df = pd.DataFrame(data["openings"])
        if not df.empty:
            from theme import COLORS, WDL, style
            n = st.slider("Top nhóm", 5, 30, 10)
            fig = px.bar(df.head(n).iloc[::-1], x="popularity_pct", y="opening_family", orientation="h",
                         color_discrete_sequence=[COLORS["primary"]],
                         labels={"popularity_pct":"Tỷ trọng (%)", "opening_family":""},
                         hover_data={"n_games": ":,.0f"})
            st.subheader("Khai cuộc phổ biến")
            fig.update_traces(texttemplate="%{x:.2f}%", textposition="outside", cliponaxis=False)
            style(fig, height=max(380, n*28), margin=dict(t=20, r=65, b=20), yaxis_title=None)
            st.plotly_chart(fig, width="stretch")
            shown = df.head(n).melt(id_vars=["opening_family"], value_vars=["white_win_pct","draw_pct","black_win_pct"],var_name="Kết quả",value_name="Tỷ lệ (%)")
            shown["Kết quả"] = shown["Kết quả"].map({"white_win_pct":"Trắng thắng","draw_pct":"Hòa","black_win_pct":"Đen thắng"})
            st.subheader("Cơ cấu kết quả thi đấu")
            outcome = px.bar(shown,x="Tỷ lệ (%)",y="opening_family",color="Kết quả",orientation="h",barmode="stack",
                             color_discrete_map=WDL)
            style(outcome, height=max(380, n*28), yaxis_title=None,
                  legend=dict(orientation="h", y=1.08, x=0), margin=dict(t=40, b=20))
            outcome.update_xaxes(range=[0, 100])
            st.plotly_chart(outcome,width="stretch")
            with st.expander("Xem bảng số liệu"):
                st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.warning("Chưa có ván đủ điều kiện cho thể thức này. Hồ sơ cá nhân vẫn hỗ trợ các thể thức khác.")
elif section == "Khai cuộc C1–C7":
    from opening_analysis import render
    a, b = st.columns(2)
    source = a.selectbox("Nguồn phân tích", ["lichess", "chesscom", "import"], format_func=SOURCE_NAMES.get)
    speed = b.selectbox("Thể thức", SPEEDS, format_func=SPEED_NAMES.get, key="cube_speed")
    payload = get("/openings/cube", {"source": source, "speed": speed})
    if payload:
        render(payload)
elif section == "Hồ sơ cá nhân":
    source = st.selectbox("Nền tảng", ["chesscom", "lichess", "import"], format_func=SOURCE_NAMES.get)
    username = st.text_input("Username", "hikaru")
    auto = st.checkbox("Tự động tải lịch sử nếu tài khoản chưa có trong kho dữ liệu", value=True,
                       help="Tải tối đa 3 tháng gần nhất, 1.000 ván/tháng, rồi công bố qua Spark/Trino. Không cần chạy backfill tổng quan trước.")
    from sync_panel import auto_sync_if_missing, player_sync
    player_sync(API, source, username)
    if username:
        data = get(f"/players/{source}/{username}")
        if data and source != "import" and auto and data["summary"].get("own_archive_games", 0) == 0:
            data = auto_sync_if_missing(API, source, username) or data
        if data:
            from player_profile_view import render
            render(data)
elif section == "Ván đấu":
    raw = st.text_input("ID ván đấu", placeholder="ví dụ 186015937976 hoặc lichess ID 8 ký tự")
    if raw:
        key = game_key_from_input(raw)
        cache = st.session_state.setdefault("game_cache", {})
        if key not in cache:
            fetched = fetch_game(key)
            if fetched:
                cache[key] = fetched
        data = cache.get(key)
        if data:
            replay_board(data, key)
        else:
            st.info("Không tìm thấy ván. Kiểm tra ID hoặc nhập dạng nền_tảng:ID.")
elif section == "Nhập dữ liệu":
    from sync_panel import backfill
    backfill(API)
elif section == "Live observer":
    from sync_panel import post
    username_live = st.text_input("Tìm ván đang chơi bằng username Lichess")
    if st.button("Tìm ván đang diễn ra") and username_live:
        found = get(f"/live-discovery/{username_live}")
        if found and found.get("ongoing"):
            st.session_state["live_game"] = found["game_id"]
        elif found:
            st.info("Tài khoản không có ván đang diễn ra; API có thể trả về ván gần nhất đã kết thúc.")
    game_id = st.text_input("Lichess game ID (8 ký tự)", key="live_game")
    a,b = st.columns(2)
    if a.button("Kết nối ván", type="primary") and game_id:
        result = post(API, f"/live-observers/{game_id}")
        if result:
            st.success("Đã yêu cầu kết nối luồng Lichess.")
    if b.button("Dừng theo dõi") and game_id:
        post(API, f"/live-observers/{game_id}", method="DELETE")
    if game_id:
        @st.fragment(run_every="3s")
        def live_panel():
            data = get(f"/live/{game_id}")
            if data:
                labels = {"observing":"Đang nhận nước đi", "connecting":"Đang kết nối", "stream_closed":"Luồng đã kết thúc", "disconnected":"Mất kết nối — bấm Kết nối ván để tiếp tục", "stopped":"Đã dừng", "failed":"Kết nối thất bại", "reconnecting":"Đang kết nối lại"}
                st.write("Trạng thái:", labels.get(data["status"], data["status"]))
                players = data.get("players", {})
                names = [players.get(c, {}).get("user", {}).get("name", c) for c in ("white", "black")]
                st.subheader(" — ".join(names))
                st.caption(f'Nhận gần nhất: {data.get("received_at", "chưa có")} · {data["source_delay"]}')
                if data.get("fen"):
                    st.image(chess.svg.board(chess.Board(data["fen"]),size=440, colors=BOARD_COLORS), width=440)
                label = data.get("opening")
                st.write("Nhãn khớp gần nhất:", f'{label["name"]} ({label["eco"]})' if label else "Chưa nhận diện")
                st.caption(f'Số sự kiện đã nhận: {data.get("received_events", 0)}')
                if data.get("ingestion_request_id"):
                    st.info("Ván đã kết thúc và được xếp hàng nhập vào kho phân tích.")
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
