import pandas as pd
from modules.technical_analysis import evaluate_technical
from modules.support_resistance import find_support_resistance

def make_trading_decision(df: pd.DataFrame, ai_result: dict) -> dict:
    last = df.iloc[-1]
    last_close = float(last["close"])
    tech = evaluate_technical(df)
    sr = find_support_resistance(df)
    score = tech["score"]
    
    # Xử lý an toàn trường hợp ai_result không có key risk_level
    risk_level = ai_result.get("risk_level", "TRUNG BÌNH") if isinstance(ai_result, dict) else "TRUNG BÌNH"
    atr = float(last.get("ATR14", last_close * 0.02))

    if score >= 3 and risk_level != "CAO":
        decision = "MUA"
        reason = "Tín hiệu kỹ thuật ủng hộ mạnh mẽ, dòng tiền tốt và rủi ro ở mức kiểm soát được."
    elif score >= 1:
        decision = "CHỜ MUA"
        reason = "Xu hướng tích cực nhưng cần kiên nhẫn chờ giá điều chỉnh về vùng hỗ trợ đẹp."
    elif score >= -1:
        decision = "GIỮ"
        reason = "Cổ phiếu đang tích lũy đi ngang, chưa xuất hiện tín hiệu vi phạm xấu."
    elif score >= -3:
        decision = "CHỜ BÁN"
        reason = "Động lượng suy yếu, ưu tiên canh các nhịp hồi phục kỹ thuật để hạ tỷ trọng."
    else:
        decision = "BÁN"
        reason = "Tín hiệu kỹ thuật vi phạm ngưỡng an toàn, áp lực bán xả lớn."

    support_price = float(sr["support"])
    resistance_price = float(sr["resistance"])

    # --- TỐI ƯU SIÊU AN TOÀN: TUYỆT ĐỐI KHÔNG SÁT KHÁNG CỰ ---
    # Khoảng cách từ kháng cự về giá đóng cửa hiện tại
    distance_to_resistance = resistance_price - last_close

    # Nếu kháng cự quá gần (khoảng cách nhỏ hơn 2 * ATR), ta hạ toàn bộ vùng mua thấp hẳn xuống
    # Cận trên vùng mua sẽ bị chặn lại cách kháng cự ít nhất một khoảng an toàn (ví dụ: cách kháng cự một đoạn ATR hoặc không vượt quá trung điểm)
    safe_ceiling_buffer = max(1.0 * atr, distance_to_resistance * 0.4)
    max_allowed_buy_price = resistance_price - safe_ceiling_buffer

    # Cận dưới bám sát hỗ trợ hoặc lùi xuống theo ATR
    buy_zone_low = round(max(support_price, last_close - 2.0 * atr), 2)
    
    # Cận trên bị chặn nghiêm ngặt không được chạm sát kháng cự
    buy_zone_high = round(min(max_allowed_buy_price, last_close - 0.2 * atr), 2)
    
    # Phòng ngừa trường hợp giá hiện tại đang nằm quá sát hỗ trợ làm cận dưới > cận trên
    if buy_zone_low >= buy_zone_high:
        buy_zone_low = round(buy_zone_high * 0.97, 2)

    buy_zone = f"{buy_zone_low:,.2f} - {buy_zone_high:,.2f}"

    confirm_price = round(last_close * 1.015, 2)
    target_price = round(resistance_price * 0.99, 2) # Mục tiêu chốt lời nằm ngay trước kháng cự
    stop_loss = round(min(support_price * 0.97, last_close - 2.5 * atr), 2)

    return {
        "decision": decision,
        "reason": reason,
        "buy_zone": buy_zone,
        "confirm_price": f"{confirm_price:,.2f}",
        "target_price": f"{target_price:,.2f}",
        "stop_loss": f"{stop_loss:,.2f}",
    }
