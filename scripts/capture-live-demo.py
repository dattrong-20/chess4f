"""Record real delayed Lichess updates through the local observer UI."""
import json, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright, expect
out=Path("artifacts/demo");out.mkdir(parents=True,exist_ok=True)
with httpx.Client(timeout=30) as client:
    response=client.get("https://lichess.org/api/tv/channels");response.raise_for_status()
    game=response.json()["blitz"]["gameId"]
with sync_playwright() as p:
    browser=p.chromium.launch()
    context=browser.new_context(viewport={"width":1440,"height":1000},record_video_dir=str(out/"video"))
    page=context.new_page();page.goto("http://127.0.0.1:8501/")
    page.get_by_test_id("stSidebar").get_by_text("Live observer",exact=True).click()
    page.get_by_label("Lichess game ID (8 ký tự)",exact=True).fill(game)
    page.get_by_role("button",name="Kết nối ván",exact=True).click()
    expect(page.get_by_test_id("stImage").locator("img")).to_be_visible(timeout=60000)
    page.get_by_test_id("stImage").scroll_into_view_if_needed()
    first=httpx.get(f"http://127.0.0.1:8000/live/{game}").json()
    page.wait_for_timeout(30000)
    last=httpx.get(f"http://127.0.0.1:8000/live/{game}").json()
    page.screenshot(path=str(out/"07-live-updating.png"))
    page.get_by_role("button",name="Dừng theo dõi",exact=True).click()
    video=page.video;context.close();video.save_as(str(out/"chess4f-live.webm"));browser.close()
result={"game_id":game,"first_events":first["received_events"],"last_events":last["received_events"],"position_changed":first.get("fen")!=last.get("fen")}
(out/"live-evidence.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
assert result["last_events"]>result["first_events"],result
print("LIVE_UI_UPDATES_VERIFIED",result)
