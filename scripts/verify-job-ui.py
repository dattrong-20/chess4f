"""Submit an unchanged demo scope through the actual browser form."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import json
root=Path("data/requests")
before={p.name for p in root.glob("*.json")}
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={"width":1440,"height":1000})
    page.goto("http://127.0.0.1:8501/")
    page.get_by_test_id("stSidebar").get_by_text("Nhập dữ liệu",exact=True).click()
    page.get_by_role("button",name="Xếp lịch nhập dữ liệu",exact=True).click()
    expect(page.get_by_text("Chờ Dagster nhận yêu cầu",exact=True)).to_be_visible(timeout=60000)
    page.screenshot(path="artifacts/demo/06-job-queued.png")
    browser.close()
new=[json.loads(p.read_text(encoding="utf-8")) for p in root.glob("*.json") if p.name not in before]
assert len(new)==1 and new[0]["payload"]["kind"]=="backfill",new
print("BROWSER_SUBMISSION_PASSED",new[0]["id"])
