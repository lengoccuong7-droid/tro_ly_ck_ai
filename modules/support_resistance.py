import pandas as pd
import numpy as np

def find_support_resistance(df: pd.DataFrame, window: int = 20) -> dict:
    # Lấy ngắn hạn hơn (ví dụ 20 phiên) và dùng phân vị thay vì min/max tuyệt đối để tránh nhiễu
    recent = df.tail(window)
    last_close = float(df["close"].iloc[-1])
    
    # Dùng phân vị 10% và 90% thay vì min/max hoàn toàn để loại bỏ các đỉnh/đáy sốc
    support = float(np.percentile(recent["low"], 10))
    resistance = float(np.percentile(recent["high"], 90))
    
    # Fallback nếu sát quá
    if support >= last_close:
        support = float(recent["low"].min())
    if resistance <= last_close:
        resistance = float(recent["high"].max())

    dist_to_support_pct = round(((last_close - support) / support) * 100, 2)
    dist_to_resistance_pct = round(((resistance - last_close) / last_close) * 100, 2)

    return {
        "support": support,
        "resistance": resistance,
        "dist_to_support_pct": dist_to_support_pct,
        "dist_to_resistance_pct": dist_to_resistance_pct
    }
