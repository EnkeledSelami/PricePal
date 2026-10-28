"""Desktop interface for PricePal."""

import csv
import queue
import threading
import tkinter as tk
import webbrowser
from collections import defaultdict
from pathlib import Path
from tkinter import messagebox, ttk

import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import main as core


BG = "#f3f6fb"
CARD = "#ffffff"
INK = "#172033"
MUTED = "#6d7890"
ACCENT = "#4263eb"
GREEN = "#16865c"


class PricePalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PricePal | Smart Price Finder")
        self.root.geometry("1120x760")
        self.root.minsize(900, 640)
        self.root.configure(bg=BG)
        self.events = queue.Queue()
        self.busy = False
        self.results = []
        self.history_rows = []
        self._style()
        self._build_shell()
        self.show_page("search")
        self.root.after(100, self._service_events)

    def _style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, fieldbackground=CARD,
                        foreground=INK, rowheight=34, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#edf1f8", foreground=MUTED,
                        font=("Segoe UI Semibold", 9), relief="flat")
        style.map("Treeview", background=[("selected", "#e7ecff")],
                  foreground=[("selected", INK)])
        style.configure("TCombobox", padding=8, font=("Segoe UI", 10))

    def _build_shell(self):
        self.sidebar = tk.Frame(self.root, bg="#18233b", width=226)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="◈  PricePal", bg="#18233b", fg="white",
                 font=("Segoe UI Semibold", 20)).pack(anchor="w", padx=24, pady=(28, 4))
        tk.Label(self.sidebar, text="SMART SHOPPING, SIMPLIFIED", bg="#18233b", fg="#9eabc5",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=27, pady=(0, 32))
        self.nav = {}
        for key, label in (("search", "⌕   Find prices"), ("history", "◷   Price history")):
            btn = tk.Button(self.sidebar, text=label, anchor="w", padx=20, pady=13,
                            relief="flat", bd=0, bg="#18233b", fg="#d8deeb",
                            activebackground="#293758", activeforeground="white",
                            font=("Segoe UI", 11), command=lambda page=key: self.show_page(page))
            btn.pack(fill="x", padx=12, pady=3)
            self.nav[key] = btn
        tk.Label(self.sidebar, text="Compare local store prices\nand keep a simple history.",
                 justify="left", bg="#18233b", fg="#9eabc5",
                 font=("Segoe UI", 9)).pack(side="bottom", anchor="w", padx=25, pady=24)

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.header = tk.Frame(self.content, bg=BG)
        self.header.pack(fill="x", padx=34, pady=(27, 16))
        self.page_title = tk.Label(self.header, text="Find the right price", bg=BG, fg=INK,
                                   font=("Segoe UI Semibold", 22))
        self.page_title.pack(anchor="w")
        self.page_subtitle = tk.Label(self.header, text="Search trusted Albanian stores in one place.",
                                      bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.page_subtitle.pack(anchor="w", pady=(5, 0))
        self.page_host = tk.Frame(self.content, bg=BG)
        self.page_host.pack(fill="both", expand=True, padx=34, pady=(0, 26))

    def show_page(self, page):
        for child in self.page_host.winfo_children():
            child.destroy()
        for key, btn in self.nav.items():
            btn.configure(bg="#293758" if key == page else "#18233b",
                          fg="white" if key == page else "#d8deeb")
        if page == "search":
            self.page_title.configure(text="Find the right price")
            self.page_subtitle.configure(text="Search trusted Albanian stores in one place.")
            self._build_search_page()
        else:
            self.page_title.configure(text="Your price history")
            self.page_subtitle.configure(text="Review saved prices and compare each store over time.")
            self._build_history_page()

    def _card(self, parent, **kwargs):
        frame = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground="#e7ebf2", **kwargs)
        return frame

    def _build_search_page(self):
        form = self._card(self.page_host)
        form.pack(fill="x", pady=(0, 16))
        tk.Label(form, text="What are you looking for?", bg=CARD, fg=INK,
                 font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=20, pady=(17, 9))
        row = tk.Frame(form, bg=CARD)
        row.pack(fill="x", padx=20, pady=(0, 17))
        self.query = tk.StringVar()
        self.query_entry = tk.Entry(row, textvariable=self.query, relief="flat", bd=0,
                                    bg="#f2f5fa", fg=INK, insertbackground=INK,
                                    font=("Segoe UI", 11))
        self.query_entry.pack(side="left", fill="x", expand=True, ipady=12, padx=(0, 10))
        self.query_entry.bind("<Return>", lambda _event: self.start_search())
        self.mode = tk.StringVar(value="Compare all")
        self.mode_box = ttk.Combobox(row, textvariable=self.mode, state="readonly", width=17,
                                     values=("Compare all", "One store"))
        self.mode_box.pack(side="left", padx=(0, 10), ipady=5)
        self.store = tk.StringVar(value="Shpresa")
        self.store_box = ttk.Combobox(row, textvariable=self.store, state="readonly", width=13,
                                      values=[name for name, _ in core.SEARCHERS.values()])
        self.store_box.pack(side="left", padx=(0, 10), ipady=5)
        self.mode_box.bind("<<ComboboxSelected>>", self._mode_changed)
        self.search_button = tk.Button(row, text="Search prices  →", command=self.start_search,
                                       bg=ACCENT, fg="white", activebackground="#3451cf",
                                       activeforeground="white", relief="flat", bd=0,
                                       padx=18, pady=11, font=("Segoe UI Semibold", 10), cursor="hand2")
        self.search_button.pack(side="left")
        self.store_box.pack_forget()

        self.status = tk.Label(self.page_host, text="Ready when you are.", bg=BG, fg=MUTED,
                               font=("Segoe UI", 9))
        self.status.pack(anchor="w", pady=(0, 10))
        self.summary = tk.Frame(self.page_host, bg=BG)
        self.summary.pack(fill="x", pady=(0, 12))
        results_card = self._card(self.page_host)
        results_card.pack(fill="both", expand=True)
        top = tk.Frame(results_card, bg=CARD)
        top.pack(fill="x", padx=18, pady=(14, 8))
        tk.Label(top, text="Results", bg=CARD, fg=INK,
                 font=("Segoe UI Semibold", 12)).pack(side="left")
        self.save_button = tk.Button(top, text="Save to history", command=self.save_results,
                                     state="disabled", bg="#e9edff", fg=ACCENT, relief="flat",
                                     padx=12, pady=7, font=("Segoe UI Semibold", 9), cursor="hand2")
        self.save_button.pack(side="right")
        self.result_table = ttk.Treeview(results_card, columns=("store", "product", "price", "date"),
                                         show="headings", selectmode="browse")
        for col, label, width in (("store", "STORE", 120), ("product", "PRODUCT", 420),
                                  ("price", "PRICE", 150), ("date", "CHECKED", 150)):
            self.result_table.heading(col, text=label)
            self.result_table.column(col, width=width, anchor="w" if col in ("store", "product") else "center")
        self.result_table.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.result_table.bind("<Double-1>", self.open_selected_result)
        self.query_entry.focus_set()

    def _mode_changed(self, _event=None):
        if self.mode.get() == "One store":
            self.store_box.pack(side="left", padx=(0, 10), ipady=5, before=self.search_button)
        else:
            self.store_box.pack_forget()

    def _product_selector(self, products, store_name, query):
        response = {"selection": None}
        ready = threading.Event()
        self.events.put(("choose", products, store_name, query, response, ready))
        ready.wait()
        return response["selection"]

    def start_search(self):
        if self.busy:
            return
        query = self.query.get().strip()
        if not query:
            messagebox.showinfo("Enter a product", "Type a product name to start searching.", parent=self.root)
            self.query_entry.focus_set()
            return
        selected = [(name, searcher) for name, searcher in core.SEARCHERS.values()]
        if self.mode.get() == "One store":
            selected = [(name, searcher) for name, searcher in selected if name == self.store.get()]
        self.results = []
        self._render_results([])
        self._summary_cards([])
        self._set_busy(True)
        self.status.configure(text="Searching stores… this can take a few seconds.", fg=ACCENT)
        threading.Thread(target=self._search_worker, args=(query, selected), daemon=True).start()

    def _search_worker(self, query, stores):
        found = []
        for store_name, searcher in stores:
            result = core.run_search(store_name, searcher, query, product_selector=self._product_selector)
            if result:
                found.append(result)
        self.events.put(("complete", found))

    def _service_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "choose":
                    _, products, store_name, query, response, ready = event
                    response["selection"] = self._choose_product_dialog(products, store_name, query)
                    ready.set()
                elif event[0] == "complete":
                    self.results = event[1]
                    self._render_results(self.results)
                    self._summary_cards(self.results)
                    self._set_busy(False)
                    if self.results:
                        self.status.configure(text=f"Found prices at {len(self.results)} store(s). Double-click a row to open the product page.", fg=GREEN)
                        self.save_button.configure(state="normal")
                    else:
                        self.status.configure(text="No prices found. Try a shorter or more specific product name.", fg=MUTED)
                        self.save_button.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._service_events)

    def _choose_product_dialog(self, products, store_name, query):
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose a product")
        dialog.geometry("560x470")
        dialog.minsize(430, 340)
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text=f"Choose a match from {store_name}", bg=BG, fg=INK,
                 font=("Segoe UI Semibold", 16)).pack(anchor="w", padx=20, pady=(18, 3))
        tk.Label(dialog, text=f"Search: {query}  ·  {len(products)} matches", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 12))
        listing = tk.Listbox(dialog, activestyle="none", selectmode="browse", relief="flat",
                             bg=CARD, fg=INK, font=("Segoe UI", 10), selectbackground="#dfe6ff",
                             selectforeground=INK, highlightthickness=1, highlightbackground="#e2e7f0")
        listing.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        for title, _url in products:
            listing.insert("end", title)
        listing.selection_set(0)
        answer = {"value": None}
        buttons = tk.Frame(dialog, bg=BG)
        buttons.pack(fill="x", padx=20, pady=(0, 18))
        def choose(_event=None):
            selected = listing.curselection()
            if selected:
                answer["value"] = products[selected[0]]
            dialog.destroy()
        tk.Button(buttons, text="Cancel", command=dialog.destroy, relief="flat", bg="#e8ecf3",
                  fg=INK, padx=14, pady=8, cursor="hand2").pack(side="right", padx=(8, 0))
        tk.Button(buttons, text="Use this product", command=choose, relief="flat", bg=ACCENT,
                  fg="white", padx=14, pady=8, cursor="hand2").pack(side="right")
        listing.bind("<Double-1>", choose)
        dialog.bind("<Return>", choose)
        dialog.wait_window()
        return answer["value"]

    def _set_busy(self, value):
        self.busy = value
        self.search_button.configure(state="disabled" if value else "normal",
                                     text="Searching…" if value else "Search prices  →")

    def _summary_cards(self, results):
        for child in self.summary.winfo_children():
            child.destroy()
        if not results:
            return
        lowest = min(results, key=lambda row: row[2])
        highest = max(results, key=lambda row: row[2])
        for title, result, color in (("LOWEST PRICE", lowest, GREEN), ("HIGHEST PRICE", highest, ACCENT)):
            card = self._card(self.summary)
            card.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(card, text=title, bg=CARD, fg=MUTED,
                     font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=15, pady=(12, 3))
            tk.Label(card, text=f"{result[2]:,} Lekë", bg=CARD, fg=color,
                     font=("Segoe UI Semibold", 17)).pack(anchor="w", padx=15)
            tk.Label(card, text=result[0], bg=CARD, fg=INK,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=15, pady=(0, 12))

    def _render_results(self, results):
        for item in self.result_table.get_children():
            self.result_table.delete(item)
        self._row_urls = {}
        for result in results:
            item = self.result_table.insert("", "end", values=(result[0], result[1],
                                        f"{result[2]:,} Lekë", f"{result[4]} {result[5]}"))
            self._row_urls[item] = result[3]

    def open_selected_result(self, _event=None):
        selection = self.result_table.selection()
        if selection:
            webbrowser.open(self._row_urls.get(selection[0], ""))

    def save_results(self):
        if not self.results:
            return
        try:
            core.save_results_to_file(self.results, str(self._history_path()))
            self.status.configure(text=f"Saved {len(self.results)} price record(s) to PriceHistory.csv.", fg=GREEN)
            self._load_history()
        except OSError as exc:
            messagebox.showerror("Could not save history", str(exc), parent=self.root)

    def _history_path(self):
        return Path(__file__).resolve().parent / "PriceHistory.csv"

    def _load_history(self):
        rows = []
        path = self._history_path()
        if path.exists():
            try:
                with path.open("r", newline="", encoding="utf-8") as file:
                    rows = [row for row in csv.DictReader(file)
                            if all(row.get(column) for column in core.CSV_COLUMNS)]
            except (OSError, csv.Error):
                rows = []
        self.history_rows = rows
        return rows

    def _build_history_page(self):
        rows = self._load_history()
        products = list(dict.fromkeys(row["Product Name"] for row in rows))
        selector_card = self._card(self.page_host)
        selector_card.pack(fill="x", pady=(0, 14))
        tk.Label(selector_card, text="Select a product", bg=CARD, fg=INK,
                 font=("Segoe UI Semibold", 11)).pack(side="left", padx=18, pady=15)
        self.history_product = tk.StringVar(value=products[-1] if products else "")
        self.history_box = ttk.Combobox(selector_card, textvariable=self.history_product,
                                        values=products, state="readonly" if products else "disabled", width=38)
        self.history_box.pack(side="left", padx=8, pady=10, ipady=4)
        self.history_box.bind("<<ComboboxSelected>>", lambda _event: self._draw_history())
        self.history_hint = tk.Label(selector_card,
                                     text=f"{len(rows)} saved observation(s)" if rows else "No saved prices yet",
                                     bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self.history_hint.pack(side="right", padx=18)
        self.chart_card = self._card(self.page_host)
        self.chart_card.pack(fill="both", expand=True)
        self.figure = Figure(figsize=(9, 4.6), dpi=100, facecolor=CARD)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=14, pady=14)
        self._draw_history()

    def _draw_history(self):
        self.figure.clear()
        product = self.history_product.get()
        rows = [row for row in self.history_rows if row["Product Name"] == product]
        if not rows:
            axis = self.figure.add_subplot(111)
            axis.set_facecolor(CARD)
            axis.text(.5, .52, "No price history for this product yet", ha="center", va="center",
                      color=MUTED, fontsize=12, transform=axis.transAxes)
            axis.axis("off")
        else:
            frame = pd.DataFrame(rows)
            frame["Price (Lekë)"] = pd.to_numeric(frame["Price (Lekë)"], errors="coerce")
            frame["DateTime"] = pd.to_datetime(frame["Date"] + " " + frame["Time"], errors="coerce")
            frame = frame.dropna(subset=["Price (Lekë)", "DateTime"]).sort_values("DateTime")
            left, right = self.figure.subplots(1, 2)
            colors = {"Shpresa": "#4263eb", "3vFejzo": "#ee8b35", "Neptun": "#27956f"}
            for site, group in frame.groupby("Site"):
                color = colors.get(site, "#8792a8")
                left.plot(group["DateTime"], group["Price (Lekë)"], marker="o", linewidth=2,
                          color=color, label=site)
            left.set_title(f"Price trend · {product}", loc="left", color=INK, fontsize=11, pad=14)
            left.set_ylabel("Price (Lekë)", color=MUTED)
            left.grid(axis="y", color="#e9edf4")
            left.legend(frameon=False)
            left.tick_params(axis="x", rotation=30, labelsize=8, colors=MUTED)
            left.tick_params(axis="y", labelsize=8, colors=MUTED)
            latest = frame.sort_values("DateTime").groupby("Site", as_index=False).tail(1)
            right.bar(latest["Site"], latest["Price (Lekë)"],
                      color=[colors.get(site, "#8792a8") for site in latest["Site"]], width=.58)
            right.set_title("Latest price by store", loc="left", color=INK, fontsize=11, pad=14)
            right.set_ylabel("Price (Lekë)", color=MUTED)
            right.set_ylim(0, max(1, latest["Price (Lekë)"].max() * 1.12))
            right.grid(axis="y", color="#e9edf4")
            right.set_axisbelow(True)
            right.tick_params(axis="x", labelsize=8, colors=MUTED)
            right.tick_params(axis="y", labelsize=8, colors=MUTED)
            for index, price in enumerate(latest["Price (Lekë)"]):
                right.text(index, price, f"{price:,.0f}", ha="center", va="bottom", fontsize=8, color=INK)
            for axis in (left, right):
                axis.spines["top"].set_visible(False)
                axis.spines["right"].set_visible(False)
                axis.spines["left"].set_color("#dce2ec")
                axis.spines["bottom"].set_color("#dce2ec")
            self.figure.tight_layout(pad=2.2)
        self.canvas.draw_idle()


def launch_gui():
    root = tk.Tk()
    PricePalApp(root)
    root.mainloop()

