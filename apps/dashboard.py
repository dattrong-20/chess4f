"""Streamlit front end: Trino-backed analytics and queued ingestion via API."""
import os

import chess
import chess.svg
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

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


SOURCE_NAMES = {"lichess": "Lichess", "chesscom": "Chess.com", "import": "PGN nhập thủ công"}
st.title("chess4f")
st.caption("Khám phá khai cuộc · Hiểu lịch sử thi đấu · Theo dõi dữ liệu")
st.sidebar.title("chess4f")
st.sidebar.caption("CHESS ANALYTICS WORKSPACE")
section = st.sidebar.radio("Không gian phân tích", ["Tổng quan", "Khai cuộc C1–C7", "Hồ sơ cá nhân", "Ván đấu", "Live observer", "Nhập dữ liệu"])
st.sidebar.info("Dữ liệu hiển thị chỉ bao gồm phần đã nhập. Tần suất lịch sử không phải xác suất thắng hay gợi ý nước tốt nhất.")
if st.sidebar.button("Đọc lại dữ liệu"):
    st.rerun()

if section == "Tổng quan":
    st.subheader("Tổng quan nguồn dữ liệu")
    source = st.selectbox("Nguồn phân tích",["lichess","chesscom","import"], format_func=SOURCE_NAMES.get)
    data = get("/overview",{"source":source})
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
                st.caption("Lịch Dagster hiện lấy tháng trước vào Chủ nhật, giới hạn 1.000 ván/lượt. Mẫu đầu tệp không đại diện toàn tháng.")
            elif source == "chesscom":
                st.write("Bộ demo ban đầu gồm lịch sử Hikaru tháng 9/2026; lịch sử đồng bộ thêm được gộp theo ID ván duy nhất. Số ván phản ánh dữ liệu đã nhập, không đại diện toàn nền tảng.")
            else:
                st.write("Nguồn PGN nhập thủ công, được phân tích riêng với hai nền tảng.")
        st.info("Biểu đồ khai cuộc: chỉ Rated Blitz đã nhận diện. Mẫu số tỷ trọng gồm mọi nhóm đủ điều kiện, không chỉ Top N.")
        df = pd.DataFrame(data["openings"])
        if not df.empty:
            n = st.slider("Top nhóm", 5, 30, 10)
            fig = px.bar(df.head(n).iloc[::-1], x="popularity_pct", y="opening_family", orientation="h",
                         color_discrete_sequence=["#3155d9"], labels={"popularity_pct":"Tỷ trọng (%)", "opening_family":""})
            st.subheader("Khai cuộc phổ biến")
            fig.update_traces(texttemplate="%{x:.2f}%", textposition="outside", cliponaxis=False)
            fig.update_layout(height=max(380, n*28), margin=dict(t=20,r=65,b=20), yaxis_title=None)
            st.plotly_chart(fig, width="stretch")
            shown = df.head(n).melt(id_vars=["opening_family"], value_vars=["white_win_pct","draw_pct","black_win_pct"],var_name="Kết quả",value_name="Tỷ lệ (%)")
            shown["Kết quả"] = shown["Kết quả"].map({"white_win_pct":"Trắng thắng","draw_pct":"Hòa","black_win_pct":"Đen thắng"})
            st.subheader("Cơ cấu kết quả thi đấu")
            outcome = px.bar(shown,x="Tỷ lệ (%)",y="opening_family",color="Kết quả",orientation="h",barmode="stack", color_discrete_map={"Trắng thắng":"#247ba0","Hòa":"#aab2bd","Đen thắng":"#ed9135"})
            outcome.update_layout(height=max(380,n*28),yaxis_title=None,legend_title_text="",legend=dict(orientation="h",y=1.1),margin=dict(t=40,b=20))
            outcome.update_xaxes(range=[0,100])
            st.plotly_chart(outcome,width="stretch")
            with st.expander("Xem bảng số liệu"):
                st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.warning("Chưa có Rated Blitz đủ điều kiện. Hồ sơ cá nhân vẫn hỗ trợ các thể thức khác.")
elif section == "Khai cuộc C1–C7":
    from opening_analysis import render
    source = st.selectbox("Nguồn phân tích", ["lichess", "chesscom", "import"], format_func=SOURCE_NAMES.get)
    payload = get("/openings/cube", {"source": source})
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
        if data and data["summary"]["games"] == 0 and auto:
            data = auto_sync_if_missing(API, source, username)
        if data:
            from player_profile_view import render
            render(data)
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
                st.image(chess.svg.board(board,size=450), width=450)
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
elif section == "Nhập dữ liệu":
    from sync_panel import backfill
    backfill(API)
elif section == "Live observer":
    st.warning("Luồng công khai Lichess có độ trễ do nguồn. Dùng để quan sát; không phải công cụ hỗ trợ người đang thi đấu.")
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
    st.caption("Luồng có độ trễ 3 nước theo Lichess. Ván kết thúc được xếp hàng nhập và công bố; không gửi nước đi hay đánh giá engine.")
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
                    st.image(chess.svg.board(chess.Board(data["fen"]),size=440), width=440)
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
