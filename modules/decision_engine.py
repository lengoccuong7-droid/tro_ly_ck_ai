import pandas as pd
from modules.technical_analysis import evaluate_technical
from modules.support_resistance import find_support_resistance

def make_trading_decision(df: pd.DataFrame, ai_result: dict) -> dict:
    last = df.iloc[-1]
    last_close = float(last["close"])
    tech = evaluate_technical(df)
    sr = find_support_resistance(df)
    score = tech["score"]
    risk_level = ai_result.get("risk_level", "TRUNG BÌNH")
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

    # --- THU HẸP VÙNG MUA & QUẢN TRỊ RỦI RO HỢP LÝ ---
    # Vùng mua xoay quanh giá hiện tại +/- 1.5% đến 2%
    buy_zone_low = round(last_close * 0.98, -2)
    buy_zone_high = round(last_close * 1.005, -2)
    
    if buy_zone_low > buy_zone_high:
        buy_zone_low = buy_zone_high

    buy_zone = f"{buy_zone_low:,.0f} - {buy_zone_high:,.0f}"

    # Cắt lỗ siết chặt ở mức 5 - 6% từ giá hiện tại
    stop_loss = round(last_close * 0.95, -2)
    
    # Chốt lời kỳ vọng R:R khoảng 1:1.5 hoặc 1:2 (+8% đến +10%)
    target_price = round(last_close * 1.09, -2)
    
    confirm_price = round(last_close * 1.01, -2)

    return {
        "decision": decision,
        "reason": reason,
        "buy_zone": buy_zone,
        "confirm_price": f"{confirm_price:,.0f}",
        "target_price": f"{target_price:,.0f}",
        "stop_loss": f"{stop_loss:,.0f}",
    }
