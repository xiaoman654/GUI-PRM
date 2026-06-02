from pathlib import Path

import numpy as np
from PIL import Image


def load_rgb(path: str | Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def pixel_change_ratio(before: str | Path, after: str | Path) -> float:
    before_arr = np.asarray(load_rgb(before), dtype=np.float32)
    after_arr = np.asarray(load_rgb(after).resize(load_rgb(before).size), dtype=np.float32)
    diff = np.abs(before_arr - after_arr).mean() / 255.0
    return float(diff)


def is_blank_or_dark(path: str | Path, dark_threshold: float = 8.0, std_threshold: float = 3.0) -> bool:
    arr = np.asarray(load_rgb(path).convert("L"), dtype=np.float32)
    return bool(arr.mean() < dark_threshold or arr.std() < std_threshold)
