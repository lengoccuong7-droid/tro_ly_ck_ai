import streamlit as st
import requests

st.set_page_config(page_title="API Mobile Test", layout="centered")

st.title("📱 Test Gọi API Trực Tuyến")
st.caption("Kiểm tra kết nối 4G/Wifi - Ép ngắt 3s chống treo App 100%")

test_url = st.text_input(
    "Nhập URL API test:", 
    value="https://api.coindesk.com/v1/bpi/currentprice.json"
)

timeout_val = st.slider("Thời gian chờ tối đa (giây):", min_value=1, max_value=5, value=3)

if st.button("🚀 BẮT ĐẦU TEST KẾT NỐI", type="primary", use_container_width=True):
    with st.spinner(f"⏳ Đang kết nối (Giới hạn {timeout_val}s)..."):
        try:
            res = requests.get(test_url, timeout=timeout_val)
            if res.status_code == 200:
                st.success("✅ KẾT NỐI THÀNH CÔNG! (Code 200)")
                try:
                    st.json(res.json())
                except:
                    st.code(res.text[:300])
            else:
                st.warning(f"⚠️ Server trả mã lỗi: {res.status_code}")

        except requests.exceptions.Timeout:
            st.error(f"⏱️ **LỖI TIMEOUT:** Server phản hồi quá {timeout_val}s. App đã tự ngắt ngầm để giữ điện thoại mượt mà, không bị treo đơ màn hình!")
        except requests.exceptions.ConnectionError:
            st.error("🔌 **LỖI MẠNG:** Không thể kết nối. Anh kiểm tra lại 4G/Wifi trên điện thoại nhé!")
        except Exception as e:
            st.error(f"❌ **LỖI:** {e}")
