"""Mo ta diem ky thuat goc cua evaluate_technical (thang -6 den +6)."""


def score_description(score: int) -> str:
    score = int(score)
    if score >= 4:
        return "TÍN HIỆU KỸ THUẬT RẤT TÍCH CỰC: nhiều điều kiện xu hướng/động lượng đang đồng thuận; vẫn cần kiểm tra điểm mua và rủi ro."
    if score >= 2:
        return "TÍCH CỰC: các chỉ báo nghiêng về xu hướng tăng, cần chờ điểm vào hợp lý."
    if score >= -1:
        return "TRUNG TÍNH: chưa có lợi thế xu hướng rõ ràng."
    if score >= -3:
        return "TIÊU CỰC: xu hướng kỹ thuật suy yếu, ưu tiên bảo toàn vốn."
    return "RẤT TIÊU CỰC: áp lực giảm chiếm ưu thế, không mở vị thế mua mới."
