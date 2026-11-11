import os
import json
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, api_key: str = None):
        """
        Khởi tạo AI Analyzer.
        Lấy API key từ tham số hoặc biến môi trường GEMINI_API_KEY.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        
        if self.api_key:
            try:
                # Khởi tạo SDK Google GenAI (Gemini)
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Lỗi khi khởi tạo Google GenAI Client: {e}")

    def analyze_stock_comprehensive(self, symbol: str, indicator_data: dict, money_flow_data: dict, score_data: dict, sr_data: dict = None) -> str:
        """
        Tổng hợp dữ liệu định lượng từ các module trong app và gửi câu lệnh tới AI.
        """
        # Nếu chưa cấu hình API Key, trả về thông báo hướng dẫn
        if not self.client:
            return (
                "⚠️ **Chưa cấu hình API Key cho AI.**\n\n"
                "Vui lòng thiết lập biến môi trường `GEMINI_API_KEY` hoặc truyền `api_key` "
                "vào khởi tạo `AIAnalyzer` để kích hoạt tính năng Siêu Trí Tuệ."
            )

        # Đóng gói ngữ cảnh chi tiết cho AI
        prompt = f"""
        Bạn là một chuyên gia phân tích đầu tư tài chính và chứng khoán hàng đầu.
        Hãy đưa ra nhận định chuyên sâu và dễ hiểu cho mã cổ phiếu **{symbol}** dựa trên các dữ liệu định lượng thực tế được trích xuất từ hệ thống bên dưới:

        1. CHỈ BÁO KỸ THUẬT (Technical Indicators):
        {json.dumps(indicator_data, ensure_ascii=False, indent=2)}

        2. DÒNG TIỀN & THOÁT KHỎI THỊ TRƯỜNG (Money Flow):
        {json.dumps(money_flow_data, ensure_ascii=False, indent=2)}

        3. ĐIỂM SỐ CỔ PHIẾU (Stock Scoring):
        {json.dumps(score_data, ensure_ascii=False, indent=2)}

        4. VÙNG HỖ TRỢ & KHÁNG CỰ (Support / Resistance):
        {json.dumps(sr_data or {}, ensure_ascii=False, indent=2)}

        ---
        YÊU CẦU TRẢ LỜI (Trình bày bằng tiếng Việt, chuẩn định dạng Markdown):
        - **1. Tổng quan xu hướng:** Xu hướng hiện tại (Ngắn/Trung hạn) và tín hiệu kỹ thuật nổi bật.
        - **2. Đánh giá Dòng tiền & Điểm số:** Phân tích xem dòng tiền lớn đang vào hay ra, điểm số định lượng phản ánh điều gì.
        - **3. Khuyến nghị hành động:** Đưa ra lời khuyên cụ thể (Mua gom / Mua gia tăng / Nắm giữ / Bán hạ tỷ trọng / Theo dõi) kèm theo các vùng giá kích hoạt (Entry, Stop-loss, Target).
        """

        try:
            # Gọi mô hình Gemini mới nhất
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            logger.error(f"Lỗi khi gọi API AI: {e}")
            return f"❌ **Đã xảy ra lỗi trong quá trình AI phân tích:** {str(e)}"
