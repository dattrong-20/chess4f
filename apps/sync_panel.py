import httpx
import streamlit as st
from datetime import date


def post(api, path, payload=None, method="POST"):
    try:
        response = httpx.request(method, api+path, json=payload, timeout=40)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        detail = exc.response.text if isinstance(exc, httpx.HTTPStatusError) else str(exc)
        st.error("Không thể gửi yêu cầu: " + detail[:500])


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
            state = item["status"]
            if state == "complete":
                st.success("Đã công bố dữ liệu. Bấm Làm mới hồ sơ để xem kết quả.")
                if st.button("Làm mới hồ sơ"):
                    del st.session_state["sync_request"]
                    st.rerun()
            elif state == "failed":
                st.error("Đồng bộ thất bại: " + item.get("error", ""))
                if st.button("Thử lại từ tháng chưa hoàn tất"):
                    retried = post(api, f"/requests/{request_id}/retry")
                    if retried:
                        st.session_state["sync_request"] = retried["id"]
                        st.rerun()
            else:
                labels = {"waiting_for_dagster":"Chờ Dagster nhận yêu cầu", "snapshot_upload":"Đưa bản dữ liệu lên MinIO", "spark_validation":"Spark xử lý và kiểm chứng", "trino_validation":"Trino kiểm chứng trước công bố"}
                st.info(labels.get(item["stage"], item["stage"]))
                st.caption("Nếu chờ lâu ở hàng đợi, hãy kiểm tra Dagster daemon/sensor đang chạy trên máy.")
            if item.get("months"):
                st.dataframe(item["months"], hide_index=True)
                if any(m.get("possibly_limited") for m in item["months"]):
                    st.caption("Có tháng chạm giới hạn ván. Đây là lịch sử giới hạn, chưa khẳng định đã tải toàn bộ; tăng phạm vi ở lượt sau nếu cần.")
        except httpx.HTTPError:
            st.warning("Chưa đọc được tiến độ. Yêu cầu đã gửi vẫn được lưu trên máy.")
    panel()


def player_sync(api, source, username):
    if source == "import":
        return
    with st.expander("Tải / cập nhật lịch sử từ nền tảng"):
        st.caption("Chọn khoảng tháng; Dagster tải, xử lý và công bố trong nền. Giới hạn áp dụng cho từng tháng; lịch sử ngoài phạm vi không bị xóa.")
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
    st.caption("Xử lý tuần tự tối đa 24 tháng/lượt. Chạy lại dùng checkpoint, không nhân đôi ID ván. Mẫu đầu tệp không đại diện toàn tháng.")
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
