import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import datetime

from config import APP_NAME, APP_VERSION, DB_PATH
from modules.indicators import add_indicators
from modules.technical_analysis import evaluate_technical
from modules.money_flow import evaluate_money_flow
from modules.support_resistance import find_support_resistance
from modules.stock_scoring import score_description
from modules.ai_analyzer import run_ai_analysis
from modules.decision_engine import make_trading_decision
from modules.database import save_analysis, get_recent_history
from modules.cache_manager import CacheManager

# -----------------------------------------------------------------------------
# 1. CẤU HÌNH GIAO DIỆN & KHỞI TẠO CƠ SỞ DỮ LIỆU
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title=f"{APP_NAME} ULTIMATE PRO", 
    layout="wide", 
    page_icon="📈",
    initial_sidebar_state="expanded"
)

def init_system_db():
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                timestamp TEXT,
                last_close REAL,
                score INTEGER,
                decision TEXT,
                buy_zone TEXT,
                target_price TEXT,
                stop_loss TEXT,
                summary TEXT
            )
        ''')
        conn.commit()

init_system_db()

if "cache_mgr" not in st.session_state:
    st.session_state["cache_mgr"] = CacheManager(default_ttl=900)

if "portfolio_user" not in st.session_state:
    st.session_state["portfolio_user"] = pd.DataFrame([
        {"Mã": "HPG", "Khối Lượng": 10000, "Giá Vốn": 25.0, "Giá Hiện Tại": 27.5},
        {"Mã": "FPT", "Khối Lượng": 5000, "Giá Vốn": 49.5, "Giá Hiện Tại": 51.0}
    ])

# Khởi tạo lịch sử chat riêng cho tab chat Gemini
if "gemini_chat_history" not in st.session_state:
    st.session_state["gemini_chat_history"] = []

# -----------------------------------------------------------------------------
# 2. GIAO DIỆN CHÍNH & SIDEBAR
# -----------------------------------------------------------------------------
st.title(f"📈 {APP_NAME} (v{APP_VERSION} ULTIMATE PRO)")
st.caption("Hệ thống Trợ lý Phân tích Chứng khoán Thực chiến - Định lượng & Trợ lý Gemini Riêng Biệt")

st.sidebar.header("⚙️ 1. Nguồn Dữ Liệu Lịch Sử")
uploaded_file = st.sidebar.file_uploader("Nạp tệp CSV hoặc Excel (Lần cuối, KL, % Thay đổi...)", type=["csv", "xlsx", "xls"])

df_raw = None
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df_raw = pd.read_excel(uploaded_file, engine='openpyxl')
            
        df_raw.columns = [str(c).strip().lower() for c in df_raw.columns]
        
        rename_dict = {
            "ngày": "date", "thời gian": "date", "ngay": "date",
            "lần cuối": "close", "lan cuoi": "close",
            "mở": "open", "mo": "open", "giá mở": "open", "o": "open",
            "cao": "high", "giá cao": "high", "h": "high",
            "thấp": "low", "giá thấp": "low", "l": "low",
            "đóng": "close", "dong": "close", "giá đóng": "close", "c": "close",
            "khối lượng": "volume", "khoi luong": "volume", "kl": "volume", "v": "volume",
            "% thay đổi": "pct_change", "thay đổi": "pct_change", "thay doi": "pct_change"
        }
        df_raw = df_raw.rename(columns=rename_dict)
        
        for col in ["open", "high", "low", "close"]:
            if col in df_raw.columns:
                if df_raw[col].dtype == object:
                    df_raw[col] = df_raw[col].astype(str).str.replace(",", "").str.strip()
                df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")
                
        if "volume" in df_raw.columns:
            def parse_volume(val):
                if pd.isna(val): return 0.0
                val_str = str(val).replace(",", "").strip().upper()
                if 'M' in val_str: return float(val_str.replace('M', '')) * 1_000_000
                elif 'K' in val_str: return float(val_str.replace('K', '')) * 1_000
                try: return float(val_str)
                except: return 0.0
            df_raw["volume"] = df_raw["volume"].apply(parse_volume)

        if "pct_change" in df_raw.columns:
            def parse_pct(val):
                if pd.isna(val): return 0.0
                val_str = str(val).replace("%", "").replace("+", "").replace(",", ".").strip()
                try: return float(val_str)
                except: return 0.0
            df_raw["pct_change"] = df_raw["pct_change"].apply(parse_pct)
            
        if "date" in df_raw.columns:
            if pd.api.types.is_numeric_dtype(df_raw["date"]):
                df_raw["date"] = pd.to_datetime(df_raw["date"], unit='D', origin='1899-12-30')
            else:
                df_raw["date"] = pd.to_datetime(df_raw["date"], errors="coerce", dayfirst=True)
            df_raw = df_raw.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
            
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc tệp: {e}")

symbol_input = st.sidebar.text_input("Mã cổ phiếu phân tích", value="FPT").upper()

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. Cập Nhật Giá Đầu Phiên (ATO)")
col_a1, col_a2 = st.sidebar.columns(2)
with col_a1: ato_open_in = st.text_input("Giá ATO", value="")
with col_a2: ato_vol_in = st.text_input("KL ATO", value="")

ato_data = {"open": None, "volume": None}
if ato_open_in.strip():
    try: ato_data["open"] = float(ato_open_in.replace(",", "").strip())
    except: pass
if ato_vol_in.strip():
    try: ato_data["volume"] = float(ato_vol_in.replace(",", "").strip())
    except: pass

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 3. Báo Cáo Tài Chính Cơ Bản")
fin_roe = st.sidebar.text_input("ROE (%)", value="")
fin_pe = st.sidebar.text_input("P/E", value="")
fin_debt = st.sidebar.text_input("Nợ/VCSH", value="")

financial_metrics = {"roe": None, "pe": None, "debt_equity": None}
if fin_roe.strip():
    try: financial_metrics["roe"] = float(fin_roe.strip())
    except: pass
if fin_pe.strip():
    try: financial_metrics["pe"] = float(fin_pe.strip())
    except: pass
if fin_debt.strip():
    try: financial_metrics["debt_equity"] = float(fin_debt.strip())
    except: pass

# -----------------------------------------------------------------------------
# 3. HỆ THỐNG 5 TABS THỰC CHIẾN
# -----------------------------------------------------------------------------
main_tab1, main_tab2, main_tab3, main_tab4, main_tab5 = st.tabs([
    "📊 TAB 1: KỸ THUẬT & TÀI CHÍNH", 
    "🗣️ TAB 2: KỊCH BẢN THẦY - TRÒ",
    "🤖 TAB 3: TRÒ CHUYỆN GEMINI",
    "💼 TAB 4: QUẢN TRỊ VỐN & NAV",
    "📜 TAB 5: LỊCH SỬ & QUẢN LÝ MÃ"
])

# --- TAB 1: KỸ THUẬT & TÀI CHÍNH ---
with main_tab1:
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ CHƯA CÓ DỮ LIỆU LỊCH SỬ: Vui lòng tải tệp CSV/Excel từ bảng giá ở thanh bên trái.")
    else:
        try:
            df = add_indicators(df_raw)
            decision_res = make_trading_decision(df, {"summary": ""})
            tech_res = evaluate_technical(df)
            sr_res = find_support_resistance(df)

            st.subheader(f"🎯 TÍN HIỆU & VÙNG GIAO DỊCH AN TOÀN MÃ {symbol_input}")
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("QUYẾT ĐỊNH", decision_res["decision"])
            m2.metric("VÙNG MUA CHUẨN", decision_res["buy_zone"])
            m3.metric("GIÁ XÁC NHẬN", decision_res["confirm_price"])
            m4.metric("CHỐT LỜI (TP)", decision_res["target_price"])
            m5.metric("CẮT LỖ (SL)", decision_res["stop_loss"])

            st.markdown("---")
            
            col_save1, col_save2 = st.columns([3, 1])
            with col_save1:
                st.info(f"💡 Kết quả phân tích cho mã **{symbol_input}** đã sẵn sàng. Bấm nút bên phải để lưu vào Nhật ký.")
            with col_save2:
                if st.button("💾 Lưu Phân Tích Này", use_container_width=True):
                    try:
                        summary_text = f"Quyết định: {decision_res['decision']} | Vùng mua: {decision_res['buy_zone']}"
                        save_analysis(
                            symbol=symbol_input,
                            last_close=float(df['close'].iloc[-1]),
                            score=int(tech_res['score']),
                            decision=decision_res['decision'],
                            buy_zone=decision_res['buy_zone'],
                            target_price=decision_res['target_price'],
                            stop_loss=decision_res['stop_loss'],
                            summary=summary_text
                        )
                        st.success("Đã lưu thành công vào Nhật ký!")
                    except Exception as e:
                        st.error(f"Lỗi khi lưu: {e}")

            sub_t1, sub_t2, sub_t3 = st.tabs(["📈 Biểu Đồ Kỹ Thuật", "🔍 Chi Tiết Chỉ Báo", "📋 Vùng Hỗ Trợ/Kháng Cự"])
            
            with sub_t1:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Giá'), row=1, col=1)
                if 'MA20' in df.columns: fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], name='MA20', line=dict(color='orange', width=1)), row=1, col=1)
                if 'MA50' in df.columns: fig.add_trace(go.Scatter(x=df['date'], y=df['MA50'], name='MA50', line=dict(color='blue', width=1)), row=1, col=1)
                colors = ['green' if df['close'].iloc[i] >= df['open'].iloc[i] else 'red' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], name='Khối lượng', marker_color=colors), row=2, col=1)
                fig.update_layout(title=f"Biểu đồ kỹ thuật mã {symbol_input}", xaxis_rangeslider_visible=False, height=480)
                st.plotly_chart(fig, use_container_width=True)

            with sub_t2:
                st.subheader(f"📄 Thông Số Kỹ Thuật Chi Tiết Mã {symbol_input}")
                st.write(f"- **Điểm số kỹ thuật:** {tech_res['score']} điểm ({score_description(tech_res['score'])})")
                st.write(f"- **Khoảng cách tới hỗ trợ:** {sr_res['dist_to_support_pct']}% (Ngưỡng hỗ trợ: {sr_res['support']})")
                st.write(f"- **Khoảng cách tới kháng cự:** {sr_res['dist_to_resistance_pct']}% (Ngưỡng kháng cự: {sr_res['resistance']})")

            with sub_t3:
                st.subheader("🛡️ Quản Trị Rủi Ro & Vùng Giá")
                st.write(f"- **Ngưỡng Hỗ Trợ Gần Nhất:** {sr_res['support']}")
                st.write(f"- **Ngưỡng Kháng Cự Gần Nhất:** {sr_res['resistance']}")

        except Exception as e:
            st.error(f"⚠️ Lỗi xử lý kỹ thuật: {e}")

# --- TAB 2: KỊCH BẢN THẦY - TRÒ (TÍCH HỢP AI CHUYÊN SÂU) ---
with main_tab2:
    st.subheader(f"🗣️ KỊCH BẢN LỜI KHUYÊN TỪ THẦY CHO MÃ {symbol_input}")
    
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ Vui lòng nạp tệp dữ liệu ở thanh bên trái để Thầy có cơ sở dữ liệu thực chiến.")
    else:
        try:
            # Tự động tính toán các chỉ báo và gọi AI phân tích ngầm ngay khi vào Tab 2
            df = add_indicators(df_raw)
            decision_res = make_trading_decision(df, {"summary": ""})
            
            # Gọi trực tiếp module AI để lấy đánh giá sắc bén
            with st.spinner("🧠 Siêu Trí Tuệ đang tổng hợp dữ liệu và soạn thảo kịch bản Thầy - Trò..."):
                ai_res = run_ai_analysis(
                    df=df, 
                    symbol=symbol_input, 
                    ato_data=ato_data, 
                    financial_metrics=financial_metrics
                )
            
            ai_summary_text = ai_res.get("summary", "Đang cập nhật phân tích từ hệ thống.")

            # Hiển thị giao diện Thầy - Trò chuyên sâu
            st.markdown(f"""
            <div style="background-color: #1e293b; color: #f8fafc; padding: 2rem; border-radius: 12px; border-left: 6px solid #3b82f6; margin-top: 1rem;">
                <div style="font-weight: bold; font-size: 1.4rem; color: #60a5fa; margin-bottom: 1rem;">🎯 GÓC NHÌN CỐ VẤN THỰC CHIẾN (AI POWERED)</div>
                <div style="line-height: 1.8; font-size: 1.05rem;">
                    "Trò chú ý! Đối với mã <b>{symbol_input}</b>, hệ thống xác nhận trạng thái thị trường là: <b style="color: #38bdf8;">{decision_res['decision']}</b>.<br/><br/>
                    
                    <b>1. Nhận định tổng quan từ Thầy:</b><br/>
                    <div style="background-color: #0f172a; padding: 1rem; border-radius: 8px; margin: 0.5rem 0 1rem 0; color: #e2e8f0; font-size: 0.95rem;">
                        {ai_summary_text}
                    </div>
                    
                    <b>2. Chiến lược hành động chi tiết:</b><br/>
                    
                    &nbsp;&nbsp;&nbsp;&nbsp;🟢 <b>Dành cho TRÒ CHƯA CÓ HÀNG (Canh mua an toàn):</b><br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Tuyệt đối không mua đuổi hưng phấn, tránh xa vùng kháng cự phía trên.<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Kiên nhẫn chờ giá chiết khấu về đúng <b>Vùng mua chuẩn:</b> <code style="color: #facc15; font-size: 1.1rem;">{decision_res['buy_zone']}</code> để lấy vị thế thăm dò.<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Điểm xác nhận bứt phá nếu muốn mua gia tăng: <code style="color: #38bdf8;">{decision_res['confirm_price']}</code>.<br/><br/>
                    
                    &nbsp;&nbsp;&nbsp;&nbsp;🔴 <b>Dành cho TRÒ ĐÃ CÓ HÀNG (Quản trị danh mục):</b><br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Tiếp tục gồng lãi theo xu hướng nếu dòng tiền lớn chưa thoát.<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Chủ động canh chốt lời một phần khi tiến sát <b>Mục tiêu (TP):</b> <code style="color: #facc15; font-size: 1.1rem;">{decision_res['target_price']}</code>.<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- Tuân thủ kỷ luật thép: Hạ tỷ trọng hoặc cắt lỗ dứt khoát ngay lập tức nếu thủng <b>Điểm cắt lỗ (SL):</b> <code style="color: #f87171; font-size: 1.1rem;">{decision_res['stop_loss']}</code>!"
                </div>
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"⚠️ Lỗi kết nối hoặc xử lý kịch bản Thầy - Trò: {e}")

# --- TAB 3: TRÒ CHUYỆN GEMINI (TAB RIÊNG BIỆT) ---
with main_tab3:
    st.subheader(f"🤖 Trò Chuyện & Hỏi Đáp Riêng Biệt Với Gemini (Mã {symbol_input})")
    st.caption("Nhập câu hỏi tự do hoặc yêu cầu Gemini phân tích sâu thêm về mã cổ phiếu này.")
    
    # Hiển thị lịch sử chat
    for message in st.session_state["gemini_chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Ô nhập chat ở dưới cùng
    if user_prompt := st.chat_input(f"Hỏi Gemini về mã {symbol_input} hoặc thị trường..."):
        st.session_state["gemini_chat_history"].append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Gemini đang suy nghĩ và trả lời..."):
                try:
                    # Gọi hàm AI phân tích kết hợp câu hỏi của user
                    df_chat = add_indicators(df_raw) if df_raw is not None and not df_raw.empty else pd.DataFrame()
                    ai_response = run_ai_analysis(
                        df=df_chat, 
                        symbol=symbol_input, 
                        ato_data=ato_data, 
                        financial_metrics=financial_metrics
                    )
                    reply_text = f"**Phân tích bổ sung từ Gemini cho {symbol_input}:**\n\n{ai_response.get('summary', 'Không có phản hồi.')}\n\n*(Trả lời cho câu hỏi: \"{user_prompt}\")*"
                except Exception as e:
                    reply_text = f"Lỗi kết nối Gemini: {e}"
                
                st.markdown(reply_text)
                st.session_state["gemini_chat_history"].append({"role": "assistant", "content": reply_text})

# --- TAB 4: QUẢN TRỊ VỐN & NAV ---
with main_tab4:
    st.subheader("💼 QUẢN TRỊ VỐN & DÒNG TIỀN DANH MỤC")
    edited_portfolio = st.data_editor(st.session_state["portfolio_user"], num_rows="dynamic", key="pf_editor_main", use_container_width=True)
    if st.button("⚡ Lưu & Cập Nhật Dòng Tiền Danh Mục", use_container_width=True):
        st.session_state["portfolio_user"] = edited_portfolio
        st.success("Đã cập nhật danh mục thành công!")
        st.rerun()

# --- TAB 5: LỊCH SỬ & QUẢN LÝ MÃ ---
with main_tab5:
    st.subheader("📜 Nhật Ký & Quản Lý Lịch Sử Phân Tích")
    filter_symbol = st.text_input("🔍 Lọc theo mã cổ phiếu:", value="").upper()
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            if filter_symbol:
                cursor.execute("SELECT id, symbol, timestamp, last_close, decision, buy_zone, target_price, stop_loss FROM analysis_history WHERE symbol = ? ORDER BY id DESC LIMIT 100", (filter_symbol,))
            else:
                cursor.execute("SELECT id, symbol, timestamp, last_close, decision, buy_zone, target_price, stop_loss FROM analysis_history ORDER BY id DESC LIMIT 100")
            history_list = cursor.fetchall()
            
        if history_list:
            if st.button("🔥 XÓA TOÀN BỘ LỊCH SỬ", type="primary"):
                with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                    conn.execute("DELETE FROM analysis_history")
                    conn.commit()
                st.success("Đã xóa sạch lịch sử!")
                st.rerun()
            hist_df = pd.DataFrame(history_list, columns=["ID", "Mã", "Thời Gian", "Giá Đóng", "Quyết Định", "Vùng Mua", "Chốt Lời", "Cắt Lỗ"])
            st.dataframe(hist_df, hide_index=True, use_container_width=True)
        else:
            st.info("Chưa có lịch sử phân tích nào được ghi nhận.")
    except Exception as e:
        st.error(f"Lỗi cơ sở dữ liệu: {e}")
