"""Phan tich tong hop cho he thong Swing.
Khong tu tao du lieu: chi su dung cac cot va chi bao co trong DataFrame.
"""
from __future__ import annotations

import math
import pandas as pd

from modules.money_flow import evaluate_money_flow
from modules.technical_analysis import evaluate_technical
from modules.support_resistance import find_support_resistance


def _num(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def run_ai_analysis(
    df: pd.DataFrame,
    symbol: str,
    ato_data: dict | None = None,
    financial_metrics: dict | None = None,
) -> dict:
    """Tong hop xu huong, dong luong, dong tien va canh bao."""
    if df is None or df.empty or len(df) < 2:
        raise ValueError("Can toi thieu 2 phien du lieu de phan tich.")

    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = _num(last.get("close"))
    if close is None or close <= 0:
        raise ValueError("Gia dong cua gan nhat khong hop le.")

    tech = evaluate_technical(df)
    flow = evaluate_money_flow(df)
    sr = find_support_resistance(df)

    ma20 = _num(last.get("MA20"))
    ma50 = _num(last.get("MA50"))
    ma200 = _num(last.get("MA200"))
    ma50_prev = _num(df.iloc[-6].get("MA50")) if len(df) >= 6 else None
    rsi = _num(last.get("RSI14"), 50.0)
    macd_hist = _num(last.get("MACD_HIST"))
    atr = _num(last.get("ATR14"), close * 0.02)
    vol_ratio = _num(flow.get("vol_ratio_20"))

    if ma20 is not None and ma50 is not None and close > ma20 > ma50:
        trend = "TĂNG MẠNH" if ma50_prev is None or ma50 > ma50_prev else "TĂNG"
    elif ma50 is not None and close > ma50:
        trend = "TĂNG"
    elif ma20 is not None and ma50 is not None and close < ma20 < ma50:
        trend = "GIẢM"
    elif ma50 is not None and close < ma50:
        trend = "GIẢM / TÍCH LŨY"
    else:
        trend = "ĐI NGANG / CHƯA RÕ"

    if rsi >= 55 and (macd_hist is None or macd_hist >= 0):
        momentum = "MẠNH"
    elif rsi < 45 or (macd_hist is not None and macd_hist < 0):
        momentum = "YẾU"
    else:
        momentum = "TRUNG BÌNH"

    warnings = []
    if rsi >= 70:
        warnings.append(f"RSI {rsi:.1f}: vùng quá mua, tránh mua đuổi.")
    if atr and close > (ma20 or close) + 1.5 * atr:
        warnings.append("Giá đang cách xa MA20 hơn 1,5 ATR: rủi ro mua đuổi.")
    if _num(sr.get("dist_to_resistance_pct"), 999) < 2:
        warnings.append("Kháng cự gần, dư địa tăng ngắn hạn bị hạn chế.")
    if flow.get("flow_status", "").lower().startswith("tiêu cực"):
        warnings.append("Dòng tiền/khối lượng đang xác nhận áp lực bán.")
    if vol_ratio is not None and vol_ratio < 0.7:
        warnings.append("Thanh khoản thấp hơn 70% trung bình 20 phiên.")
    if not warnings:
        warnings.append("Chưa phát hiện cảnh báo kỹ thuật nổi bật từ dữ liệu hiện có.")

    ato_summary = "Chưa có dữ liệu ATO."
    if isinstance(ato_data, dict):
        ato_open = _num(ato_data.get("open"))
        ato_volume = _num(ato_data.get("volume"))
        if ato_open is not None and ato_open > 0:
            gap = (ato_open / close - 1) * 100
            ato_summary = f"Giá ATO {ato_open:,.2f}, gap {gap:+.2f}%"
            if ato_volume is not None:
                ato_summary += f", KL ATO {ato_volume:,.0f}"
            if gap >= 1.5:
                warnings.append("ATO gap tăng mạnh; cần chờ xác nhận, không mua đuổi đầu phiên.")
            elif gap <= -1.5:
                warnings.append("ATO gap giảm mạnh; cần đánh giá lại áp lực cung đầu phiên.")

    fin_summary = "Chưa nhập dữ liệu tài chính cơ bản."
    if isinstance(financial_metrics, dict):
        valid = [f"{k}: {v}" for k, v in financial_metrics.items() if v is not None]
        if valid:
            fin_summary = " | ".join(valid)

    score = int(tech.get("score", 0))
    if score <= -3 or trend.startswith("GIẢM"):
        risk_level = "CAO"
    elif score >= 3 and rsi < 70 and not flow.get("flow_status", "").lower().startswith("tiêu cực"):
        risk_level = "THẤP"
    else:
        risk_level = "TRUNG BÌNH"

    return {
        "symbol": str(symbol).upper(),
        "trend": trend,
        "momentum": momentum,
        "flow_summary": flow.get("flow_status", "Chưa xác định"),
        "vol_ratio_20": vol_ratio,
        "rsi14": rsi,
        "atr14": atr,
        "risk_level": risk_level,
        "counter_arguments": warnings,
        "ato_summary": ato_summary,
        "fin_summary": fin_summary,
        "technical_score_raw": score,
        "technical_signals": tech.get("signals", []),
        "support_resistance": sr,
    }
