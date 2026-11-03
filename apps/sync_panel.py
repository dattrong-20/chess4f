import httpx
import streamlit as st
from datetime import date


def post(api, path, payload=None, method="POST"):
    try:
        response = httpx.request(method, api+path, json=payload, timeout=40)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        st.error("Không thể gửi yêu cầu: " + str(detail)[:500])
    except httpx.HTTPError as exc:
        st.error("Không thể gửi yêu cầu: " + str(exc)[:500])


def progress(api):
    request_id = st.session_state.get("sync_request")
    if not request_id:
        return
    @st.fragment(run_every="5s")
    def panel():
        try:
            response = httpx.get(api+f"/requests/{request_id}", timeout=20)
            response.raise_for_status()
            item = response.json()
        except httpx.HTTPError:
            st.info("Đang tải…")
            return
        state = item["status"]
        if state == "complete":
            # Show the refreshed profile immediately instead of a button.
            st.session_state.pop("sync_request", None)
            st.session_state.pop("auto_syncing", None)
            st.rerun(scope="app")
        elif state == "failed":
            st.error("Đồng bộ thất bại: " + item.get("error", ""))
            if st.button("Thử lại"):
                retried = post(api, f"/requests/{request_id}/retry")
                if retried:
                    st.session_state["sync_request"] = retried["id"]
                    st.rerun()
        else:
            st.info("Đang tải…")
    panel()


def player_sync(api, source, username):
    if source == "import":
        return
    with st.expander("Tải / cập nhật lịch sử từ nền tảng"):
        today = date.today()
        month = f"{today.year-1}-12" if today.month == 1 else f"{today.year}-{today.month-1:02}"
        with st.form("sync-player"):
            a,b = st.columns(2)
            start = a.text_input("Từ tháng (YYYY-MM)", month)
            end = b.text_input("Đến tháng (YYYY-MM)", month)
            limit = st.number_input("Tối đa ván mỗi tháng", 1, 10000, 1000, 100)
            if st.form_submit_button("Đồng bộ lịch sử", type="primary"):
                result = post(api, "/requests", dict(kind="player", source=source, username=username, start=start, end=end, limit=limit))
                if result:
                    st.session_state["sync_request"] = result["id"]
    progress(api)


def backfill(api):
    st.subheader("Nhập lịch sử Lichess theo tháng")
    with st.form("backfill"):
        a,b = st.columns(2)
        start = a.text_input("Từ tháng", "2026-09")
        end = b.text_input("Đến tháng", "2026-10")
        limit = st.number_input("Giới hạn ván mỗi tháng", 1, 10000, 1000, 100)
        if st.form_submit_button("Xếp lịch nhập dữ liệu"):
            result = post(api,"/requests",dict(kind="backfill",source="lichess",start=start,end=end,limit=limit))
            if result:
                st.session_state["sync_request"] = result["id"]
    progress(api)


def shift_month(month, delta):
    year, mon = (int(part) for part in month.split("-"))
    total = year * 12 + mon - 1 + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def active_player_request(api, source, username):
    """Return a queued/running sync for this exact player, if one exists."""
    try:
        response = httpx.get(api + "/requests", params={"limit": 100}, timeout=20)
        response.raise_for_status()
        items = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    for item in items:
        payload = item.get("payload", {})
        if (item.get("status") in ("queued", "running")
                and payload.get("kind") == "player"
                and payload.get("source") == source
                and payload.get("username") == username.lower()):
            return item
    return None


def auto_sync_if_missing(api, source, username, months=3, limit=1000):
    """Queue one bounded history download when a profile is absent.

    Returns None while work is queued/running (do not render an empty profile).
    The manual form stays available for a different range or a larger cap.
    """
    if source == "import" or not username:
        return None
    from chess4f.sources import previous_month

    end = previous_month()
    start = shift_month(end, -(months - 1))
    key = (source, username.lower())
    attempted = st.session_state.setdefault("auto_sync_attempted", set())
    active = active_player_request(api, source, username)
    if active:
        attempted.add(key)
        st.session_state["sync_request"] = active["id"]
        if st.session_state.get("auto_syncing") != active["id"]:
            st.session_state["auto_syncing"] = active["id"]
            st.rerun()
        return None
    if key in attempted:
        st.info("Không tìm thấy ván nào trong khoảng mặc định. Mở form phía trên để chọn khoảng tháng hoặc giới hạn khác.")
        return None
    result = post(api, "/requests", dict(kind="player", source=source, username=username,
                                        start=start, end=end, limit=limit))
    if not result:
        return None
    attempted.add(key)
    st.session_state["sync_request"] = result["id"]
    st.session_state["auto_syncing"] = result["id"]
    st.info(f"Chưa có dữ liệu cho {username}. Đang tự động tải lịch sử {start} → {end} "
            f"(tối đa {limit:,} ván/tháng). Quá trình gồm tải, Delta, Spark và Trino nên có thể mất vài phút.")
    st.rerun()
