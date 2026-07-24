from __future__ import annotations

from datetime import datetime, timezone

import customtkinter as ctk

from formatting import color_for, format_countdown, format_reset_time
from usage_client import UsageData, UsageError

ctk.set_appearance_mode("dark")


class _Row:
    """Tek bir limit satırı: etiket + çubuk + yüzde + geri sayım."""

    def __init__(self, parent, title: str):
        self.title = ctk.CTkLabel(parent, text=title, anchor="w", font=("Segoe UI", 12, "bold"))
        self.bar = ctk.CTkProgressBar(parent, height=12)
        self.bar.set(0)
        self.info = ctk.CTkLabel(parent, text="—", anchor="w", font=("Segoe UI", 11))
        self.window = None  # type: ignore
        # Saat metni sadece anahtar değişince hesaplanır; anahtar bir
        # döngü boyunca sabit kalır (5 saatte / haftada bir).
        self._reset_key = None
        self._reset_text = ""
        self._last_info = None

    def grid(self, r: int):
        self.title.grid(row=r, column=0, sticky="w", padx=10, pady=(6, 0))
        self.bar.grid(row=r + 1, column=0, sticky="ew", padx=10)
        self.info.grid(row=r + 2, column=0, sticky="w", padx=10, pady=(0, 4))

    def set(self, window):
        self.window = window
        if window is None:
            self.bar.set(0)
            self.info.configure(text="—")
            # Önbellek temizlenmezse aynı resets_at ile gelen sonraki
            # geçerli veri aynı metni üretir, yazma koruması devreye
            # girer ve satır "—" takılı kalır.
            self._reset_key = None
            self._reset_text = ""
            self._last_info = None
            return
        self.bar.set(window.utilization / 100)
        self.bar.configure(progress_color=color_for(window.utilization))
        self.refresh_countdown()

    def refresh_countdown(self, now=None):
        if self.window is None:
            return
        now = now or datetime.now(timezone.utc)
        resets_at = self.window.resets_at
        expired = int((resets_at - now).total_seconds()) <= 0

        # Yerel gün anahtarda: gün adının varlığı gece yarısı bayatlar.
        # Süresi dolmuşluk anahtarda: dolduğunda saat metni boşalmalı
        # ama resets_at ve yerel gün değişmez.
        key = (resets_at, now.astimezone().date(), expired)
        if key != self._reset_key:
            self._reset_key = key
            self._reset_text = format_reset_time(resets_at, now)

        text = f"%{self.window.utilization:.0f}   ⟳ {format_countdown(resets_at, now)}"
        if self._reset_text:
            text += f" · {self._reset_text}"

        # Geri sayım dakika hassasiyetinde; saniyede bir yazmanın anlamı yok.
        if text != self._last_info:
            self._last_info = text
            self.info.configure(text=text)


class UsageApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Claude Kullanımı")
        self.geometry("260x235")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)
        self.on_refresh = None
        self._data = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Claude Kullanımı", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="↻", width=28, command=self._refresh_clicked).grid(row=0, column=1)

        self.five = _Row(self, "5 saatlik")
        self.five.grid(1)
        self.seven = _Row(self, "Haftalık")
        self.seven.grid(4)

        self.status = ctk.CTkLabel(self, text="yükleniyor…", anchor="w", font=("Segoe UI", 10), text_color="gray")
        self.status.grid(row=7, column=0, sticky="w", padx=10, pady=(2, 6))

    def _refresh_clicked(self):
        if self.on_refresh:
            self.on_refresh()

    def render(self, data: UsageData):
        self._data = data
        self.five.set(data.five_hour)
        self.seven.set(data.seven_day)
        self.status.configure(text=f"güncellendi: {data.fetched_at.astimezone().strftime('%H:%M')}", text_color="gray")

    def render_error(self, err: UsageError):
        self.status.configure(text=err.message, text_color="#e74c3c")

    def tick(self):
        self.five.refresh_countdown()
        self.seven.refresh_countdown()
