"""核心：開活動頁 → 找「登錄」按鈕 → 點擊 → 判斷結果 → 寫 results.csv"""
import csv, datetime as dt, pathlib, random, re, sys, time
import yaml
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# 打包成 exe 時，資料放在 exe 旁邊
BASE = pathlib.Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
CONFIG = BASE / "campaigns.yaml"
PROFILE = BASE / "browser-profile"   # 保存登入狀態（cookie），勿外流
LOG = BASE / "results.csv"
SHOTS = BASE / "screenshots"

DEFAULTS = {
    "button_texts": ["立即登錄", "我要登錄", "登錄活動", "活動登錄", "點我登錄", "馬上登錄"],
    "confirm_texts": ["確定", "確認", "同意並登錄", "我同意"],
    "done_texts": ["已登錄", "登錄成功", "完成登錄", "您已完成登錄", "已完成登錄"],
    "login_texts": ["請先登入", "會員登入", "請登入"],
}


def load_config():
    if not CONFIG.exists():
        return dict(DEFAULTS), []
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    return {**DEFAULTS, **(cfg.get("defaults") or {})}, cfg.get("campaigns") or []


def save_config(defaults, campaigns):
    CONFIG.write_text(yaml.safe_dump({"defaults": defaults, "campaigns": campaigns},
                                     allow_unicode=True, sort_keys=False), encoding="utf-8")


def open_browser(p, headless):
    """優先用 Windows 內建 Edge（免另外下載瀏覽器），沒有再用 Chrome / Playwright Chromium。"""
    for channel in ("msedge", "chrome", None):
        try:
            return p.chromium.launch_persistent_context(
                PROFILE, headless=headless, locale="zh-TW", channel=channel, viewport=None)
        except Exception:
            continue
    raise RuntimeError("找不到 Edge / Chrome，請執行：python -m playwright install chromium")


def _has(page, texts):
    try:
        body = page.inner_text("body", timeout=10_000)
    except PWTimeout:
        return None
    return next((t for t in texts if t in body), None)


def _click(page, texts, timeout=3_000):
    for frame in page.frames:                       # 含 iframe
        for t in texts:
            loc = frame.get_by_text(re.compile(re.escape(t))).filter(visible=True)
            for i in range(loc.count()):
                try:
                    el = loc.nth(i)
                    el.scroll_into_view_if_needed(timeout=timeout)
                    el.click(timeout=timeout)
                    return t
                except PWTimeout:
                    continue
    return None


def register(page, c):
    page.goto(c["url"], wait_until="domcontentloaded", timeout=45_000)
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except PWTimeout:
        pass
    if hit := _has(page, c["done_texts"]):
        return "已登錄過", hit
    if hit := _has(page, c["login_texts"]):
        return "需要登入", f"頁面顯示「{hit}」，請先按「開瀏覽器登入」"
    clicked = _click(page, c["button_texts"])
    if not clicked:
        return "找不到按鈕", "請在活動設定補上按鈕文字"
    time.sleep(1.5)
    _click(page, c["confirm_texts"], timeout=1_500)  # 自訂確認彈窗（沒有就略過）
    time.sleep(2)
    if hit := _has(page, c["done_texts"]):
        return "成功", f"點「{clicked}」→ {hit}"
    if hit := _has(page, c["login_texts"]):
        return "需要登入", f"點擊後要求登入（{hit}）"
    return "待確認", f"已點「{clicked}」但沒看到成功字樣，請看截圖"


def run_all(campaigns, defaults, headless=False, on_result=print, should_stop=lambda: False):
    SHOTS.mkdir(exist_ok=True)
    new = not LOG.exists()
    with sync_playwright() as p, LOG.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["時間", "活動", "結果", "說明", "網址"])
        ctx = open_browser(p, headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("dialog", lambda d: d.accept())     # 原生 alert/confirm 自動按確定
        for i, c in enumerate(campaigns):
            if should_stop():
                break
            c = {**defaults, **c}
            try:
                status, note = register(page, c)
            except Exception as e:
                status, note = "錯誤", str(e).splitlines()[0]
            ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            safe = re.sub(r"[^\w一-鿿-]", "_", c["name"])
            try:
                page.screenshot(path=str(SHOTS / f"{ts[:10]}_{safe}.png"), full_page=True)
            except Exception:
                pass
            w.writerow([ts, c["name"], status, note, page.url]); f.flush()
            on_result(i, c["name"], status, note)
            time.sleep(random.uniform(3, 6))        # 放慢節奏，避免被判定異常流量
        ctx.close()


def login_session(start_url="https://www.momoshop.com.tw/"):
    """開有畫面的瀏覽器讓本人登入（含 OTP），關掉瀏覽器視窗即保存。"""
    with sync_playwright() as p:
        ctx = open_browser(p, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(start_url)
        ctx.wait_for_event("close", timeout=0)


if __name__ == "__main__":   # 給排程用：python promo_core.py  （背景執行全部活動）
    d, cs = load_config()
    run_all(cs, d, headless=True)
