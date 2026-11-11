pimport os
import json
import logging

# Cấu hình logging để dễ dàng theo dõi lỗi nếu có
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_ai_analysis(df, symbol, ato_data=None, financial_metrics=None):
    """
    Hàm gọi trực tiếp AI để phân tích dữ liệu chứng khoán thực chiến.
    Tự động trích xuất các thông số kỹ thuật mới nhất từ DataFrame và kết hợp với dữ liệu tài chính/ATO.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    # Nếu chưa cấu hình API Key, trả về cảnh báo trực tiếp
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
        # Khởi tạo Google GenAI Client
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Trích xuất dòng dữ liệu mới nhất từ DataFrame lịch sử
        last_row = df.iloc[-1]
        
        # Đóng gói dữ liệu ngữ cảnh (Context)
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
        
        # Xây dựng câu lệnh (Prompt) thông minh chuyên sâu cho chuyên gia tài chính
        prompt = f"""
        Bạn là một chuyên gia phân tích đầu tư chứng khoán thực chiến hàng đầu.
        Hãy phân tích ngắn gọn, sắc bén và đưa ra nhận định chuyên sâu cho mã cổ phiếu **{symbol}** dựa trên các dữ liệu định lượng thực tế sau:

        {json.dumps(context_data, ensure_ascii=False, indent=2)}

        ---
        Yêu cầu trả về kết quả bằng tiếng Việt, chuẩn định dạng Markdown, bao gồm:
        1. **Nhận định xu hướng & Sức mạnh giá hiện tại** của mã.
        2. **Đánh giá dòng tiền & Yếu tố tài chính cơ bản** (nếu có).
        3. **Cảnh báo rủi ro / Phản biện bẫy giá** (ít nhất 2 điểm lưu ý quan trọng dành cho nhà đầu tư).
        """
        
        # Gọi mô hình Gemini mới nhất
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        ai_text = response.text
        
        # Trả về kết quả đúng cấu trúc mà App.py đang mong đợi
        return {
            "summary": ai_text,
            "fin_summary": f"ROE: {financial_metrics.get('roe', 'N/A')}% | P/E: {financial_metrics.get('pe', 'N/A')} | Nợ/VCSH: {financial_metrics.get('debt_equity', 'N/A')}",
            "flow_summary": f"Khối lượng khớp lệnh gần nhất: {last_row.get('volume', 0):,.0f}, giá đóng cửa: {last_row.get('close', 0):,.2f}",
            "counter_arguments": [
                "⚠️ Thận trọng với các biến động bất thường của thị trường chung (VN-Index).",
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
