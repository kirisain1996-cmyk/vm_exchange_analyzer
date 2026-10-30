"""Сеанс обмена (временная шкала записей) и логика плеера. Без зависимостей от Qt."""
from __future__ import annotations

from bisect import bisect_right
from datetime import time

DAY_MS = 86_400_000
SPEEDS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)
NORMAL_SPEED_IDX = SPEEDS.index(1.0)


def time_to_ms(t: time) -> int:
    return ((t.hour * 60 + t.minute) * 60 + t.second) * 1000 + t.microsecond // 1000


class Session:
    """Записи + шкала времени в миллисекундах от первой записи.

    Переход через полночь учитывается (время идёт дальше, а не «прыгает» назад).
    Небольшие обратные скачки времени сглаживаются: шкала всегда неубывающая.
    """

    def __init__(self, records: list):
        self.records = records
        self.start_clock_ms = time_to_ms(records[0].time) if records else 0
        self.t_ms: list[int] = []
        offset, prev_abs = 0, None
        for r in records:
            a = time_to_ms(r.time)
            if prev_abs is not None and a < prev_abs - DAY_MS // 2:
                offset += DAY_MS
            prev_abs = a
            t = a + offset - self.start_clock_ms
            if self.t_ms and t < self.t_ms[-1]:
                t = self.t_ms[-1]
            self.t_ms.append(t)
        self.duration_ms = self.t_ms[-1] if self.t_ms else 0
        self.by_array: dict[int, list[int]] = {}
        for i, r in enumerate(records):
            self.by_array.setdefault(r.array_id, []).append(i)

    def __len__(self) -> int:
        return len(self.records)

    def index_at(self, t_ms: float) -> int:
        """Индекс последней записи со временем <= t_ms (-1, если таких нет)."""
        return bisect_right(self.t_ms, t_ms) - 1

    def last_of_array(self, array_id: int, idx: int) -> int | None:
        """Индекс последней записи массива среди записей 0..idx."""
        lst = self.by_array.get(array_id)
        if not lst or idx < 0:
            return None
        k = bisect_right(lst, idx) - 1
        return lst[k] if k >= 0 else None

    def clock_text(self, t_ms: float) -> str:
        total = int(self.start_clock_ms + t_ms) % DAY_MS
        return f"{total // 3600000:02d}:{(total // 60000) % 60:02d}:{(total // 1000) % 60:02d}.{total % 1000:03d}"


def format_elapsed(ms: float) -> str:
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h}:{m:02d}:{s:02d}.{milli:03d}" if h else f"{m:02d}:{s:02d}.{milli:03d}"


def format_speed(speed: float) -> str:
    return f"×{speed:g}"


class Player:
    """Часы воспроизведения: t — время сеанса в мс. 1× = секунда сеанса за секунду реального времени."""

    def __init__(self, duration_ms: int = 0):
        self.duration_ms = duration_ms
        self.t = 0.0
        self.speed_idx = NORMAL_SPEED_IDX
        self.playing = False
        self.loop = False

    @property
    def speed(self) -> float:
        return SPEEDS[self.speed_idx]

    def set_duration(self, duration_ms: int) -> None:
        self.duration_ms = duration_ms
        self.t = 0.0
        self.playing = False

    def seek(self, ms: float) -> None:
        self.t = min(max(0.0, ms), float(self.duration_ms))

    def toggle(self) -> None:
        if self.playing:
            self.playing = False
            return
        if self.duration_ms <= 0:
            return
        if self.t >= self.duration_ms:      # дошли до конца — начинаем сначала
            self.t = 0.0
        self.playing = True

    def faster(self) -> None:
        self.speed_idx = min(self.speed_idx + 1, len(SPEEDS) - 1)

    def slower(self) -> None:
        self.speed_idx = max(self.speed_idx - 1, 0)

    def tick(self, dt_ms: float) -> bool:
        """Продвинуть часы на dt_ms реального времени. True — время изменилось."""
        if not self.playing:
            return False
        self.t += dt_ms * self.speed
        if self.t >= self.duration_ms:
            if self.loop and self.duration_ms > 0:
                self.t %= self.duration_ms
            else:
                self.t = float(self.duration_ms)
                self.playing = False
        return True
