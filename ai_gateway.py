import streamlit as st
import google.generativeai as genai

# Cấu hình trang Streamlit
st.set_page_config(page_title="Stock AI Intelligence Layer", page_icon="📈")

st.title("📈 Trợ Lý Chứng Khoán Thông Minh (AI Layer)")

# Lấy API Key từ cấu hình ẩn (Secrets) của Streamlit Cloud hoặc nhập trực tiếp
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = st.text_input("Nhập Gemini API Key của bạn:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    
    # Ô nhập yêu cầu từ người dùng
    user_input = st.text_area(
        "Nhập lệnh của bạn:",
        placeholder="Ví dụ: Mua giúp tôi 100 cổ phiếu VCB giá 85"
    )

    if st.button("🚀 Phân Tích & Thực Thi", type="primary"):
        if not user_input:
            st.warning("Vui lòng nhập nội dung yêu cầu!")
        else:
            with st.spinner("AI đang xử lý ý định giao dịch..."):
                try:
                    # Dùng Gemini AI phân tích
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    prompt = f"""
                    Bạn là một trợ lý giao dịch chứng khoán thông minh. Hãy phân tích câu nói sau của người dùng: "{user_input}"
                    Và trích xuất ra định dạng JSON gồm các trường:
                    - action: (BUY / SELL / CHECK_RISK / UNKNOWN)
                    - stock_symbol: Mã cổ phiếu (ví dụ: VCB, FPT,...) nếu có
                    - quantity: Số lượng cổ phiếu (số nguyên) nếu có
                    - target_price: Giá mục tiêu nếu có
                    Chỉ trả về JSON thuần túy, không kèm giải thích.
                    """
                    
                    response = model.generate_content(prompt)
                    
                    st.success("✨ Phân tích thành công!")
                    st.code(response.text.strip(), language="json")
                    
                except Exception as e:
                    st.error(f"Đã có lỗi xảy ra: {str(e)}")
else:
    st.info("💡 Vui lòng cung cấp Gemini API Key để bắt đầu.")
