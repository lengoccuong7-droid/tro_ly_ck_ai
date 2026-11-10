import pandas as pd
from modules.technical_analysis import evaluate_technical
from modules.support_resistance import find_support_resistance

def make_trading_decision(df: pd.DataFrame, ai_result: dict) -> dict:
    last = df.iloc[-1]
    # Lấy giá đóng cửa linh hoạt cả chữ thường lẫn hoa
    last_close = float(last.get("close", last.get("Close", 0)))
    
    # Đảm bảo an toàn nếu module trả về dict hoặc object
    tech = evaluate_technical(df)
    score = tech.get("score", 0) if isinstance(tech, dict) else 0
    
    risk_level = ai_result.get("risk_level", "TRUNG BÌNH")
    atr = float(last.get("ATR14", last_close * 0.02))

    # --- XỬ LÝ ĐA ĐỊNH DẠNG CHO HỖ TRỢ / KHÁNG CỰ (`sr`) ---
    sr = find_support_resistance(df)
    supports = []
    resistances = []
    
    if isinstance(sr, dict):
        supports = sr.get("supports", [])
        resistances = sr.get("resistances", [])
    elif isinstance(sr, (list, tuple)) and len(sr) == 2:
        supports, resistances = sr
    elif isinstance(sr, (list, tuple)):
        supports = [x for x in sr if x < last_close]
        resistances = [x for x in sr if x > last_close]

    # Lọc các mức hỗ trợ thực tế nằm dưới giá hiện tại
    valid_supports = [s for s in supports if s < last_close]
    nearest_support = max(valid_supports) if valid_supports else round(last_close * 0.98, -2)

    # Lọc các mức kháng cự thực tế nằm trên giá hiện tại
    valid_resistances = [r for r in resistances if r > last_close]
    nearest_resistance = min(valid_resistances) if valid_resistances else round(last_close * 1.06, -2)

    # --- QUYẾT ĐỊNH GIAO DỊCH ---
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

    # --- THIẾT LẬP VÙNG GIÁ (Dùng -2 để chuẩn bước giá hàng trăm VND) ---
    buy_zone_low = round(nearest_support, -2)
    buy_zone_high = round(nearest_support * 1.015, -2)
    if buy_zone_low > buy_zone_high:
        buy_zone_low = buy_zone_high

    buy_zone = f"{buy_zone_low:,.0f} - {buy_zone_high:,.0f}"
    
    # Quản trị rủi ro dựa trên ATR và Hỗ trợ
    stop_loss = round(min(nearest_support * 0.98, last_close - (1.5 * atr)), -2)
    target_price = round(nearest_resistance, -2)
    confirm_price = round(last_close * 1.01, -2)

    return {
        "decision": decision,
        "reason": reason,
        "buy_zone": buy_zone,
        "confirm_price": confirm_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
    }
