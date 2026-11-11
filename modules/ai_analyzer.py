import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_ai_analysis(df, symbol, ato_data=None, financial_metrics=None):
    """
    Hàm gọi trực tiếp AI để phân tích dữ liệu chứng khoán thực chiến, sắc bén,
    có lọc khoảng cách an toàn so với kháng cự.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return {
            "summary": "⚠️ Chưa thiết lập biến môi trường `GEMINI_API_KEY`. Vui lòng cấu hình API Key để kích hoạt phân tích AI sâu.",
            "fin_summary": f"ROE: {financial_metrics.get('roe', 'N/A')}, P/E: {financial_metrics.get('pe', 'N/A')}",
            "flow_summary": "Dữ liệu dòng tiền hoạt động bình thường.",
            "counter_arguments": [
                "Cần cấu hình API Key từ Google AI Studio.",
                "Đảm bảo biến môi trường được thiết lập đúng trên hệ thống."
            ]
        }
    
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        last_row = df.iloc[-1]
        
        context_data = {
            "symbol": symbol,
            "date": str(last_row['date']) if 'date' in last_row else "N/A",
            "close_price": float(last_row['close']) if 'close' in last_row else 0.0,
            "volume": float(last_row['volume']) if 'volume' in last_row else 0.0,
            "ma20": float(last_row['MA20']) if 'MA20' in last_row else "N/A",
            "ma50": float(last_row['MA50']) if 'MA50' in last_row else "N/A",
            "ato_data": ato_data or {},
            "financial_metrics": financial_metrics or {}
        }
        
        prompt = f"""
        Bạn là một chuyên gia phân tích đầu tư chứng khoán thực chiến cực kỳ sắc bén và kỷ luật.
        Hãy phân tích sắc sảo mã cổ phiếu **{symbol}** dựa trên dữ liệu định lượng thực tế:

        {json.dumps(context_data, ensure_ascii=False, indent=2)}

        ---
        Yêu cầu trả về bằng tiếng Việt, định dạng Markdown:
        1. **Đánh giá xu hướng & Sức mạnh dòng tiền hiện tại**: Phân tích rõ phe mua hay phe bán đang chiếm ưu thế.
        2. **Định giá & Sức khỏe tài chính**: Nhận định ngắn gọn dựa trên ROE, P/E (nếu có).
        3. **Chiến lược giá & Cảnh báo bẫy giá (Bull/Bear Trap)**: Tuyệt đối không khuyến khích mua đuổi sát vùng kháng cự. Chỉ mở mua khi có chiết khấu an toàn về vùng hỗ trợ.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        ai_text = response.text
        
        return {
            "summary": ai_text,
            "fin_summary": f"ROE: {financial_metrics.get('roe', 'N/A')}% | P/E: {financial_metrics.get('pe', 'N/A')} | Nợ/VCSH: {financial_metrics.get('debt_equity', 'N/A')}",
            "flow_summary": f"Khối lượng khớp lệnh gần nhất: {last_row.get('volume', 0):,.0f}, giá đóng cửa: {last_row.get('close', 0):,.2f}",
            "counter_arguments": [
                "⚠️ Tuyệt đối không mua đuổi khi giá đang áp sát vùng kháng cự mạnh.",
                "🛡️ Luôn tuân thủ tuyệt đối nguyên tắc quản trị rủi ro và điểm cắt lỗ (Stop-loss)."
            ]
        }
        
    except Exception as e:
        logger.error(f"Lỗi gọi trực tiếp AI: {e}")
        return {
            "summary": f"❌ Đã xảy ra lỗi trong quá trình kết nối tới AI: {str(e)}",
            "fin_summary": "Không thể tổng hợp do lỗi kết nối.",
            "flow_summary": "Không xác định.",
            "counter_arguments": [
                "Kiểm tra lại đường truyền internet.",
                "Xác thực lại hiệu lực của Google Gemini API Key."
            ]
        }
