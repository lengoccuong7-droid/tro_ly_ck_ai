from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import google.generativeai as genai

# Khởi tạo ứng dụng FastAPI làm lớp Middleware
app = FastAPI(title="AI Intelligence Layer cho App Chứng Khoán")

# Cấu hình API Key cho Gemini (lấy từ biến môi trường)
# genai.configure(api_key=os.environ["GEMINI_API_KEY"])
genai.configure(api_key="YOUR_GEMINI_API_KEY") # Thay bằng key của bạn

# Khái báo cấu trúc dữ liệu đầu vào từ phía Frontend/Người dùng
class UserRequest(BaseModel):
    user_input: str  # Ví dụ: "Mua giúp tôi 100 cổ phiếu VCB giá 85" hoặc "Kiểm tra rủi ro danh mục"
    user_token: str  # Token xác thực tài khoản của hệ thống cũ

@app.post("/smart-execute")
async def smart_execute(req: UserRequest):
    try:
        # BƯỚC 1: Dùng AI (Gemini) để phân tích ý định và trích xuất tham số
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Bạn là một trợ lý giao dịch chứng khoán thông minh. Hãy phân tích câu nói sau của người dùng: "{req.user_input}"
        Và trích xuất ra định dạng JSON gồm các trường:
        - action: (BUY / SELL / CHECK_RISK / UNKNOWN)
        - stock_symbol: Mã cổ phiếu (ví dụ: VCB, FPT,...) nếu có
        - quantity: Số lượng cổ phiếu (số nguyên) nếu có
        - target_price: Giá mục tiêu nếu có
        Chỉ trả về JSON thuần túy, không kèm giải thích.
        """
        
        response = model.generate_content(prompt)
        ai_parsed_data = response.text.strip()
        
        # (Thực tế bạn sẽ parse chuỗi JSON này ra thành dict Python)
        
        # BƯỚC 2: Gọi đến Hệ thống/Module cũ (Legacy Backend) của bạn
        # Ở đây bạn dùng 'user_token' để gọi API module giao dịch cũ đã có sẵn
        # legacy_response = call_old_trading_module(req.user_token, ai_parsed_data)

        # BƯỚC 3: Trả kết quả thông minh về cho giao diện người dùng
        return {
            "status": "success",
            "message": "AI đã xử lý và chuyển tiếp yêu cầu thành công tới hệ thống giao dịch.",
            "ai_intent_analyzed": ai_parsed_data,
            # "legacy_system_result": legacy_response
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
