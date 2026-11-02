"""活動自動登錄小幫手（電腦版 GUI）"""
import os, queue, subprocess, sys, threading, tkinter as tk, webbrowser
from tkinter import ttk, messagebox, simpledialog
import promo_core as core

BUSY_BTNS = []


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("活動自動登錄小幫手")
        self.geometry("920x620")
        self.q, self.stop_flag = queue.Queue(), False
        self.defaults, self.campaigns = core.load_config()
        self._build()
        self._refresh()
        self.after(200, self._poll)

    # ---------- 版面 ----------
    def _build(self):
        top = ttk.Frame(self, padding=8); top.pack(fill="x")
        for text, cmd in [("開瀏覽器登入", self.on_login), ("全部登錄", self.on_run_all),
                          ("登錄選取的", self.on_run_sel), ("停止", self.on_stop)]:
            b = ttk.Button(top, text=text, command=cmd); b.pack(side="left", padx=3)
            if text != "停止":
                BUSY_BTNS.append(b)
        self.headless = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="背景執行（不顯示瀏覽器）", variable=self.headless).pack(side="left", padx=10)
        ttk.Button(top, text="建立每日排程", command=self.on_schedule).pack(side="right", padx=3)
        ttk.Button(top, text="開截圖資料夾", command=lambda: self._open(core.SHOTS)).pack(side="right", padx=3)

        add = ttk.LabelFrame(self, text="新增活動", padding=8); add.pack(fill="x", padx=8)
        ttk.Label(add, text="名稱").grid(row=0, column=0)
        self.e_name = ttk.Entry(add, width=22); self.e_name.grid(row=0, column=1, padx=4)
        ttk.Label(add, text="網址").grid(row=0, column=2)
        self.e_url = ttk.Entry(add, width=60); self.e_url.grid(row=0, column=3, padx=4)
        ttk.Button(add, text="新增", command=self.on_add).grid(row=0, column=4, padx=3)
        ttk.Button(add, text="批次貼上網址", command=self.on_bulk).grid(row=0, column=5, padx=3)

        mid = ttk.Frame(self, padding=8); mid.pack(fill="both", expand=True)
        cols = ("name", "url", "status", "note")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, t, w in zip(cols, ("活動", "網址", "結果", "說明"), (160, 300, 80, 330)):
            self.tree.heading(c, text=t); self.tree.column(c, width=w, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", self.on_edit_buttons)
        side = ttk.Frame(mid); side.pack(side="left", fill="y", padx=6)
        ttk.Button(side, text="刪除", command=self.on_delete).pack(fill="x", pady=2)
        ttk.Button(side, text="開啟網頁", command=self.on_open_url).pack(fill="x", pady=2)
        ttk.Button(side, text="設定按鈕字", command=self.on_edit_buttons).pack(fill="x", pady=2)

        self.status = tk.StringVar(value="就緒。第一次使用請先按「開瀏覽器登入」。")
        ttk.Label(self, textvariable=self.status, padding=6, relief="sunken").pack(fill="x", side="bottom")

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(self.campaigns):
            self.tree.insert("", "end", iid=str(i), values=(c["name"], c["url"], "", ""))

    def _save(self):
        core.save_config(self.defaults, self.campaigns)

    @staticmethod
    def _open(path):
        path.mkdir(exist_ok=True)
        os.startfile(path) if sys.platform == "win32" else subprocess.Popen(["xdg-open", path])

    # ---------- 活動清單 ----------
    def on_add(self):
        url = self.e_url.get().strip()
        if not url.startswith("http"):
            return messagebox.showwarning("提醒", "請輸入 http 開頭的網址")
        self.campaigns.append({"name": self.e_name.get().strip() or f"活動 {len(self.campaigns)+1}", "url": url})
        self.e_name.delete(0, "end"); self.e_url.delete(0, "end")
        self._save(); self._refresh()

    def on_bulk(self):
        txt = simpledialog.askstring("批次貼上", "一行一個網址（可整段貼上）：", parent=self)
        if not txt:
            return
        urls = [w for w in txt.split() if w.startswith("http")]
        for u in urls:
            self.campaigns.append({"name": f"活動 {len(self.campaigns)+1}", "url": u})
        self._save(); self._refresh()
        self.status.set(f"已加入 {len(urls)} 筆")

    def _selected(self):
        return sorted(int(i) for i in self.tree.selection())

    def on_delete(self):
        for i in reversed(self._selected()):
            del self.campaigns[i]
        self._save(); self._refresh()

    def on_open_url(self):
        for i in self._selected():
            webbrowser.open(self.campaigns[i]["url"])

    def on_edit_buttons(self, _evt=None):
        sel = self._selected()
        if not sel:
            return
        c = self.campaigns[sel[0]]
        cur = "、".join(c.get("button_texts", self.defaults["button_texts"]))
        txt = simpledialog.askstring("登錄按鈕文字", f"「{c['name']}」頁面上登錄按鈕的字（用、分隔）：",
                                     initialvalue=cur, parent=self)
        if txt:
            c["button_texts"] = [t.strip() for t in txt.replace(",", "、").split("、") if t.strip()]
            self._save()

    # ---------- 執行 ----------
    def _busy(self, on):
        for b in BUSY_BTNS:
            b.state(["disabled"] if on else ["!disabled"])

    def _thread(self, fn):
        self._busy(True); self.stop_flag = False
        def wrap():
            try:
                fn()
                self.q.put(("done", None))
            except Exception as e:
                self.q.put(("error", str(e)))
        threading.Thread(target=wrap, daemon=True).start()

    def on_login(self):
        self.status.set("瀏覽器已開啟：請登入 momo 及各銀行網站（可開新分頁），完成後直接關閉瀏覽器視窗。")
        self._thread(core.login_session)

    def _run(self, idxs):
        if not idxs:
            return messagebox.showinfo("提醒", "沒有可執行的活動")
        items = [self.campaigns[i] for i in idxs]
        for i in idxs:
            self.tree.set(str(i), "status", "排隊中"); self.tree.set(str(i), "note", "")
        self.status.set(f"執行中… 共 {len(items)} 筆")
        def cb(k, name, status, note):
            self.q.put(("row", (idxs[k], status, note)))
        self._thread(lambda: core.run_all(items, self.defaults, self.headless.get(), cb, lambda: self.stop_flag))

    def on_run_all(self):
        self._run(list(range(len(self.campaigns))))

    def on_run_sel(self):
        self._run(self._selected())

    def on_stop(self):
        self.stop_flag = True
        self.status.set("收到停止，跑完目前這筆就結束…")

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "row":
                    i, st, note = data
                    self.tree.set(str(i), "status", st); self.tree.set(str(i), "note", note)
                elif kind == "done":
                    self._busy(False); self.status.set(f"完成。結果記錄在 {core.LOG}")
                elif kind == "error":
                    self._busy(False); self.status.set("發生錯誤"); messagebox.showerror("錯誤", data)
        except queue.Empty:
            pass
        self.after(200, self._poll)

    # ---------- Windows 排程 ----------
    def on_schedule(self):
        if sys.platform != "win32":
            return messagebox.showinfo("提醒", "排程功能僅支援 Windows")
        t = simpledialog.askstring("每日排程", "每天幾點自動登錄？(HH:MM)", initialvalue="09:07", parent=self)
        if not t:
            return
        if getattr(sys, "frozen", False):
            cmd = f'"{sys.executable}" --auto'
        else:
            pyw = sys.executable.replace("python.exe", "pythonw.exe")
            cmd = f'"{pyw}" "{core.BASE / "promo_core.py"}"'
        r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", t,
                            "/TN", "PromoAutoRegister", "/TR", cmd], capture_output=True, text=True)
        messagebox.showinfo("排程", "已建立每日排程" if r.returncode == 0 else r.stderr or r.stdout)


if __name__ == "__main__":
    if "--auto" in sys.argv:                 # exe 被排程呼叫時：不開視窗，背景跑全部
        d, cs = core.load_config()
        core.run_all(cs, d, headless=True)
    else:
        App().mainloop()
