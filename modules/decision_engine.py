"""Bo may quyet dinh Swing: tach xu huong, diem mua va hanh dong voi vi the."""
from __future__ import annotations

import math
import pandas as pd

from modules.technical_analysis import evaluate_technical
from modules.money_flow import evaluate_money_flow
from modules.support_resistance import find_support_resistance


def _num(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _fmt(value):
    return f"{value:,.2f}" if value is not None and math.isfinite(value) else "N/A"


def make_trading_decision(
    df: pd.DataFrame,
    ai_result: dict | None = None,
    capital_vnd: float = 100_000_000,
    risk_per_trade_pct: float = 1.0,
    max_allocation_pct: float = 20.0,
    price_multiplier: float = 1_000.0,
    lot_size: int = 100,
) -> dict:
    """Tra ve khuyen nghi, muc gia va kich thuoc vi the.

    price_multiplier=1000 mac dinh vi du lieu gia chung khoan VN thuong la nghin dong.
    Neu file gia la VND/co phieu, truyen price_multiplier=1.
    """
    if df is None or len(df) < 20:
        raise ValueError("Can toi thieu 20 phien du lieu de tao khuyen nghi Swing.")

    last = df.iloc[-1]
    close = _num(last.get("close"))
    if close is None or close <= 0:
        raise ValueError("Gia dong cua khong hop le.")

    tech = evaluate_technical(df)
    flow = evaluate_money_flow(df)
    sr = find_support_resistance(df)
    raw_score = int(tech.get("score", 0))
    # evaluate_technical hien co thang -6 den +6. Quy doi minh bach sang 0-100.
    score_100 = max(0, min(100, round((raw_score + 6) / 12 * 100)))

    ma20 = _num(last.get("MA20"), close)
    ma50 = _num(last.get("MA50"), close)
    rsi = _num(last.get("RSI14"), 50.0)
    atr = _num(last.get("ATR14"), close * 0.02)
    atr = max(atr or close * 0.02, close * 0.003)
    macd_hist = _num(last.get("MACD_HIST"))
    vol_ratio = _num(flow.get("vol_ratio_20"))
    support = _num(sr.get("support"), close * 0.95)
    resistance = _num(sr.get("resistance"), close * 1.05)

    # Xac dinh xu huong dua tren cau truc MA, khong chi dua vao mot chi bao.
    ma50_5 = _num(df.iloc[-6].get("MA50")) if len(df) >= 6 else None
    if close > ma20 > ma50 and (ma50_5 is None or ma50 >= ma50_5):
        trend = "TĂNG MẠNH"
    elif close > ma50:
        trend = "TĂNG"
    elif close < ma20 < ma50:
        trend = "GIẢM"
    elif close < ma50:
        trend = "GIẢM / SUY YẾU"
    else:
        trend = "ĐI NGANG"

    momentum = "MẠNH" if rsi >= 55 and (macd_hist is None or macd_hist >= 0) else (
        "YẾU" if rsi < 45 or (macd_hist is not None and macd_hist < 0) else "TRUNG BÌNH"
    )
    flow_text = flow.get("flow_status", "Trung tính")
    flow_negative = str(flow_text).lower().startswith("tiêu cực")

    # Vung mua: neo vao MA20 va ho tro, tranh dat vung mua cao hon gia hien tai.
    anchor = min(close, ma20) if ma20 and ma20 > 0 else close
    zone_low = max(support, anchor - 0.60 * atr)
    zone_high = min(close, anchor + 0.20 * atr)
    if zone_low > zone_high:
        zone_low = max(close - 1.0 * atr, support * 0.99)
        zone_high = close
    zone_low = max(0.01, min(zone_low, zone_high))

    # Stop-loss duoi ho tro/duoi bien dong ATR; muc tieu toi thieu 2R neu khang cu qua gan.
    stop_loss = min(
    support * 0.985,
    close - 1.5 * atr
)
stop_loss = max(0.01, stop_loss)
    entry_reference = (zone_low + zone_high) / 2
    if entry_reference <= stop_loss:
        stop_loss = max(0.01, entry_reference - 1.5 * atr)

    risk_per_share = max(entry_reference - stop_loss, 0.01)
    if resistance > entry_reference:
    target_price = resistance
    else:
        target_price = entry_reference + 2.0 * risk_per_share

    reward_risk = (
        (target_price - entry_reference) / risk_per_share
        if risk_per_share > 0 else 0.0
    )
    distance_to_ma20_atr = (close - ma20) / atr if atr > 0 else 0.0
    resistance_distance = _num(sr.get("dist_to_resistance_pct"), 99.0)
    overbought = rsi >= 70
    extended = distance_to_ma20_atr > 1.5
    near_resistance = resistance_distance < 2.0
    trend_positive = trend in ("TĂNG MẠNH", "TĂNG")
    near_buy_zone = (zone_low - 0.25 * atr) <= close <= (zone_high + 0.25 * atr)

    reasons = []
    if trend_positive:
        reasons.append(f"Cấu trúc xu hướng {trend.lower()}.")
    else:
        reasons.append(f"Xu hướng hiện tại: {trend.lower()}.")
    reasons.append(f"Động lượng {momentum.lower()} (RSI {rsi:.1f}).")
    reasons.append(f"Dòng tiền: {flow_text}.")
    if overbought:
        reasons.append("RSI vào vùng quá mua, không mua đuổi.")
    if extended:
        reasons.append("Giá đã kéo xa MA20 theo ATR, ưu tiên chờ điều chỉnh.")
    if near_resistance:
        reasons.append("Kháng cự gần, tỷ lệ lợi nhuận/rủi ro có thể không còn hấp dẫn.")
    if not near_buy_zone:
        reasons.append("Giá chưa nằm gần vùng mua dự kiến; chờ điều chỉnh về vùng giá thay vì mua đuổi.")
    if flow_negative:
        reasons.append("Dòng tiền tiêu cực làm giảm độ tin cậy của tín hiệu tăng.")

    if trend_positive and score_100 >= 67 and not flow_negative and not overbought and not extended and not near_resistance and near_buy_zone and reward_risk >= 1.5:
        decision = "MUA THĂM DÒ"
        decision_color = "success"
        reasons.append("Điều kiện xu hướng, điểm mua và tỷ lệ lợi nhuận/rủi ro đang đồng thuận.")
    elif trend_positive and score_100 >= 58:
        decision = "CHỜ ĐIỂM MUA"
        decision_color = "info"
        reasons.append("Xu hướng tích cực nhưng chưa có điểm vào đủ an toàn; không mua đuổi.")
    elif trend in ("GIẢM", "GIẢM / SUY YẾU") and score_100 < 50:
        decision = "KHÔNG MUA"
        decision_color = "danger"
        reasons.append("Xu hướng/điểm số chưa ủng hộ mở vị thế mới.")
    else:
        decision = "THEO DÕI"
        decision_color = "warning"
        reasons.append("Chờ thêm xác nhận từ giá, xu hướng và thanh khoản.")

    if close < ma50 or raw_score <= -3:
        holding_action = "GIẢM TỶ TRỌNG / ĐÁNH GIÁ LẠI"
    elif trend_positive and score_100 >= 58:
        holding_action = "TIẾP TỤC NẮM GIỮ, DỜI STOP THEO XU HƯỚNG"
    else:
        holding_action = "THEO DÕI, CHƯA TĂNG TỶ TRỌNG"

    # Tinh khoi luong theo rui ro 1% NAV va tran giai ngan 20% NAV.
    risk_budget = capital_vnd * risk_per_trade_pct / 100.0
    max_allocation = capital_vnd * max_allocation_pct / 100.0
    price_vnd = entry_reference * price_multiplier
    risk_share_vnd = risk_per_share * price_multiplier
    qty_by_risk = int(risk_budget // risk_share_vnd) if risk_share_vnd > 0 else 0
    qty_by_capital = int(max_allocation // price_vnd) if price_vnd > 0 else 0
    raw_qty = max(0, min(qty_by_risk, qty_by_capital))
    quantity = (raw_qty // lot_size) * lot_size if lot_size > 0 else raw_qty
    estimated_value = quantity * price_vnd
    estimated_risk = quantity * risk_share_vnd

    warnings = []
    if len(df) < 60:
        warnings.append("Dữ liệu dưới 60 phiên: hỗ trợ/kháng cự và xu hướng dài hạn còn hạn chế.")
    if vol_ratio is None:
        warnings.append("Thiếu khối lượng hoặc VOL_MA20; đánh giá dòng tiền chưa đầy đủ.")
    if ai_result and ai_result.get("counter_arguments"):
        warnings.extend(ai_result["counter_arguments"])

    return {
        "decision": decision,
        "decision_color": decision_color,
        "holding_action": holding_action,
        "reason": " ".join(reasons),
        "reasons": reasons,
        "trend": trend,
        "momentum": momentum,
        "flow_status": flow_text,
        "technical_score_raw": raw_score,
        "score_100": score_100,
        "score_scale_note": "Quy đổi từ thang điểm kỹ thuật -6 đến +6 sang 0-100.",
        "buy_zone_low": round(zone_low, 2),
        "buy_zone_high": round(zone_high, 2),
        "buy_zone": f"{_fmt(zone_low)} - {_fmt(zone_high)}",
        "confirm_price": _fmt(close),
        "target_price_value": round(target_price, 2),
        "target_price": _fmt(target_price),
        "stop_loss_value": round(stop_loss, 2),
        "stop_loss": _fmt(stop_loss),
        "support": support,
        "resistance": resistance,
        "reward_risk": round(reward_risk, 2),
        "capital_vnd": float(capital_vnd),
        "risk_budget_vnd": round(risk_budget),
        "max_allocation_vnd": round(max_allocation),
        "suggested_quantity": quantity,
        "estimated_position_value_vnd": round(estimated_value),
        "estimated_loss_at_stop_vnd": round(estimated_risk),
        "price_multiplier": price_multiplier,
        "warnings": list(dict.fromkeys(warnings)),
        "technical_signals": tech.get("signals", []),
        "flow_details": flow,
        "support_resistance": sr,
    }
