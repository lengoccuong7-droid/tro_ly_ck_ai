import pandas as pd
from modules.technical_analysis import evaluate_technical
from modules.support_resistance import find_support_resistance

def make_trading_decision(df: pd.DataFrame, ai_result: dict) -> dict:
    last = df.iloc[-1]
    last_close = float(last["close"])
    tech = evaluate_technical(df)
    sr = find_support_resistance(df)  # Giả sử trả về dict hoặc list các mức hỗ trợ/kháng cự
    score = tech["score"]
    risk_level = ai_result.get("risk_level", "TRUNG BÌNH")
    atr = float(last.get("ATR14", last_close * 0.02))

    # --- 1. XÁC ĐỊNH HỖ TRỢ VÀ KHÁNG CỰ TỪ `sr` ---
    # Tùy thuộc vào cấu trúc trả về của find_support_resistance(df), ví dụ trả về dict: {"supports": [...], "resistances": [...]}
    supports = sr.get("supports", [last_close * 0.95]) if isinstance(sr, dict) else [last_close * 0.95]
    resistances = sr.get("resistances", [last_close * 1.05]) if isinstance(sr, dict) else [last_close * 1.05]
    
    # Lấy mức hỗ trợ gần nhất nằm dưới giá hiện tại, nếu không có lấy giá hiện tại trừ 2%
    valid_supports = [s for s in supports if s < last_close]
    nearest_support = max(valid_supports) if valid_supports else round(last_close * 0.98, -2)

    # Lấy mức kháng cự gần nhất nằm trên giá hiện tại
    valid_resistances = [r for r in resistances if r > last_close]
    nearest_resistance = min(valid_resistances) if valid_resistances else round(last_close * 1.06, -2)

    # --- 2. QUYẾT ĐỊNH GIAO DỊCH ---
    if score >= 3 and risk_level != "CAO":
        decision = "MUA"
        reason = "Tín hiệu kỹ thuật ủng hộ mạnh mẽ, dòng tiền tốt và rủi ro ở mức kiểm soát được."
    elif score >= 1:
        decision = "CHỜ MUA"
        reason = f"Xu hướng tích cực, chờ giáhạ về vùng hỗ trợ quanh {nearest_support:,.0f} để gom hàng."
    elif score >= -1:
        decision = "GIỮ"
        reason = "Cổ phiếu đang tích lũy đi ngang, chưa xuất hiện tín hiệu vi phạm xấu."
    elif score >= -3:
        decision = "CHỜ BÁN"
        reason = f"Động lượng suy yếu, áp sát kháng cự {nearest_resistance:,.0f}, ưu tiên canh hạ tỷ trọng."
    else:
        decision = "BÁN"
        reason = "Tín hiệu kỹ thuật vi phạm ngưỡng an toàn, thủng hỗ trợ mạnh."

    # --- 3. THIẾT LẬP VÙNG GIÁ DỰA TRÊN HỖ TRỢ / KHÁNG CỰ ---
    # Vùng mua xoay quanh hỗ trợ thực tế (ví dụ: từ hỗ trợ đến cao hơn 1%)
    buy_zone_low = round(nearest_support, -2)
    buy_zone_high = round(nearest_support * 1.015, -2)
    
    if buy_zone_low > buy_zone_high:
        buy_zone_low = buy_zone_high

    buy_zone = f"{buy_zone_low:,.0f} - {buy_zone_high:,.0f}"

    # Cắt lỗ siết chặt ngay dưới vùng hỗ trợ (ví dụ: thấp hơn hỗ trợ 1.5 - 2%)
    stop_loss = round(nearest_support * 0.98, -2)
    
    # Chốt lời hướng tới kháng cự gần nhất hoặc tối ưu R:R 1:2
    target_price = round(nearest_resistance, -2)
    
    confirm_price = round(last_close * 1.01, -2)

    return {
        "decision": decision,
        "reason": reason,
        "buy_zone": buy_zone,
        "confirm_price": f"{confirm_price:,.0f}",
        "target_price": f"{target_price:,.0f}",
        "stop_loss": f"{stop_loss:,.0f}",
    }
