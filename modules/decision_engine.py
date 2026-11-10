import pandas as pd  # Sửa lại chữ i thường
from modules.technical_analysis import evaluate_technical
from modules.support_resistance import find_support_resistance

def make_trading_decision(df: pd.DataFrame, ai_result: dict) -> dict:
    last = df.iloc[-1]
    last_close = float(last["close"])
    tech = evaluate_technical(df)
    sr = find_support_resistance(df)
    score = tech["score"]
    risk_level = ai_result.get("risk_level", "TRUNG BÌNH")
    
    # Sử dụng thực tế ATR để quản trị rủi ro linh hoạt theo biến động mã cổ phiếu
    atr = float(last.get("ATR14", last_close * 0.02))

    # Xử lý vùng Hỗ trợ / Kháng cự từ `sr` (giả định trả về dict hoặc list)
    supports = sr.get("supports", [last_close * 0.95]) if isinstance(sr, dict) else [last_close * 0.95]
    resistances = sr.get("resistances", [last_close * 1.05]) if isinstance(sr, dict) else [last_close * 1.05]
    
    valid_supports = [s for s in supports if s < last_close]
    nearest_support = max(valid_supports) if valid_supports else round(last_close * 0.98, 2)

    valid_resistances = [r for r in resistances if r > last_close]
    nearest_resistance = min(valid_resistances) if valid_resistances else round(last_close * 1.06, 2)

    # Đưa ra quyết định
    if score >= 3 and risk_level != "CAO":
        decision = "MUA"
        reason = "Tín hiệu kỹ thuật ủng hộ mạnh mẽ, dòng tiền tốt và rủi ro ở mức kiểm soát được."
    elif score >= 1:
        decision = "CHỜ MUA"
        reason = f"Xu hướng tích cực, chờ giá điều chỉnh về vùng hỗ trợ quanh {nearest_support:,.0f}."
    elif score >= -1:
        decision = "GIỮ"
        reason = "Cổ phiếu đang tích lũy đi ngang, chưa xuất hiện tín hiệu vi phạm xấu."
    elif score >= -3:
        decision = "CHỜ BÁN"
        reason = f"Động lượng suy yếu, áp sát kháng cự {nearest_resistance:,.0f}, canh hạ tỷ trọng."
    else:
        decision = "BÁN"
        reason = "Tín hiệu kỹ thuật vi phạm ngưỡng an toàn, áp lực bán xả lớn."

    # Thiết lập giá (Giữ dạng float để tiện tính toán ở các module khác, format chuỗi khi hiển thị UI)
    buy_zone_low = round(nearest_support, 2)
    buy_zone_high = round(nearest_support * 1.015, 2)
    if buy_zone_low > buy_zone_high:
        buy_zone_low = buy_zone_high

    buy_zone = f"{buy_zone_low:,.0f} - {buy_zone_high:,.0f}"
    
    # Dùng ATR kết hợp hỗ trợ để siết chặt cắt lỗ thực tế (ví dụ: thấp hơn hỗ trợ hoặc cách 1.5*ATR)
    stop_loss = round(min(nearest_support * 0.98, last_close - (1.5 * atr)), 2)
    target_price = round(nearest_resistance, 2)
    confirm_price = round(last_close * 1.01, 2)

    return {
        "decision": decision,
        "reason": reason,
        "buy_zone": buy_zone,
        "confirm_price": confirm_price,   # Trả về dạng số để dễ xử lý logic tiếp theo
        "target_price": target_price,
        "stop_loss": stop_loss,
    }
