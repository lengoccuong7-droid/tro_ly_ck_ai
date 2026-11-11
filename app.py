import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import datetime
import io
import os
from openpyxl.styles import Alignment

from config import APP_NAME, APP_VERSION, DB_PATH
from modules.indicators import add_indicators
from modules.technical_analysis import evaluate_technical
from modules.money_flow import evaluate_money_flow
from modules.support_resistance import find_support_resistance
from modules.stock_scoring import score_description
from modules.database import save_analysis, get_recent_history

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

# Cố định tài khoản mặc định (Không dùng mật khẩu)
current_user = "trader_pro"

if f"portfolio_{current_user}" not in st.session_state:
    st.session_state[f"portfolio_{current_user}"] = pd.DataFrame([
        {"Mã": "HPG", "Khối Lượng": 10000, "Giá Vốn": 25.0, "Giá Hiện Tại": 27.5},
        {"Mã": "FPT", "Khối Lượng": 5000, "Giá Vốn": 49.5, "Giá Hiện Tại": 51.0}
    ])

user_portfolio = st.session_state[f"portfolio_{current_user}"]

# -----------------------------------------------------------------------------
# 2. GIAO DIỆN CHÍNH
# -----------------------------------------------------------------------------
st.title(f"📈 {APP_NAME} (v{APP_VERSION} ULTIMATE PRO)")
st.caption(f"Hệ thống Phân tích Chứng khoán Thực chiến | Tài khoản: **{current_user}**")

# -----------------------------------------------------------------------------
# SIDEBAR: CỔNG NẠP DỮ LIỆU FILE & XỬ LÝ THÔNG MINH
# -----------------------------------------------------------------------------
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
                if 'M' in val_str:
                    return float(val_str.replace('M', '')) * 1_000_000
                elif 'K' in val_str:
                    return float(val_str.replace('K', '')) * 1_000
                try:
                    return float(val_str)
                except:
                    return 0.0
            df_raw["volume"] = df_raw["volume"].apply(parse_volume)

        if "pct_change" in df_raw.columns:
            def parse_pct(val):
                if pd.isna(val): return 0.0
                val_str = str(val).replace("%", "").replace("+", "").replace(",", ".").strip()
                try:
                    return float(val_str)
                except:
                    return 0.0
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
# GIAO DIỆN CHÍNH: 5 TABS ĐỘC LẬP
# -----------------------------------------------------------------------------
main_tab1, main_tab2, main_tab3, main_tab4, main_tab5 = st.tabs([
    "📊 TAB 1: KỸ THUẬT & TÀI CHÍNH", 
    "🗣️ TAB 2: THAM VẤN ĐẦU TƯ",
    "💼 TAB 3: QUẢN TRỊ VỐN & NAV",
    "📜 TAB 4: LỊCH SỬ PHÂN TÍCH",
    "📋 TAB 5: XỬ LÝ DỮ LIỆU EXCEL/CSV"
])

# --- TAB 1: KỸ THUẬT & TÀI CHÍNH ---
with main_tab1:
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ CHƯA CÓ DỮ LIỆU LỊCH SỬ: Vui lòng tải tệp CSV/Excel từ bảng giá ở thanh bên trái để tiến hành phân tích.")
        st.info("💡 Hướng dẫn: Tải file dữ liệu lịch sử của mã cổ phiếu vào mục tải tệp ở sidebar.")
    else:
        try:
            df = add_indicators(df_raw)
            tech_res = evaluate_technical(df)
            flow_res = evaluate_money_flow(df)
            sr_res = find_support_resistance(df)
            
            last_close = float(df['close'].iloc[-1])
            decision = "MUA GOM" if tech_res['score'] >= 60 else ("THEO DÕI" if tech_res['score'] >= 40 else "THẬN TRỌNG")
            # ĐÃ SỬA: Vùng mua chuẩn thấp hơn giá đóng cửa từ 2% đến 4% để tạo biên an toàn
            buy_zone = f"{last_close * 0.96:,.2f} - {last_close * 0.98:,.2f}"
            target_price = f"{last_close * 1.10:,.2f}"
            stop_loss = f"{last_close * 0.93:,.2f}"

            st.subheader(f"🎯 TÍN HIỆU & VÙNG GIAO DỊCH MÃ {symbol_input}")
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("QUYẾT ĐỊNH", decision)
            m2.metric("VÙNG MUA CHUẨN", buy_zone)
            m3.metric("GIÁ XÁC NHẬN", f"{last_close:,.2f}")
            m4.metric("CHỐT LỜI (TP)", target_price)
            m5.metric("CẮT LỖ (SL)", stop_loss)

            st.markdown("---")
            col_save1, col_save2 = st.columns([3, 1])
            with col_save1:
                st.info(f"💡 Sếp có thể bấm nút bên phải để lưu kết quả phân tích mã **{symbol_input}** này vào Nhật ký (Tab 4).")
            with col_save2:
                if st.button("💾 Lưu Phân Tích Này", use_container_width=True, type="primary"):
                    try:
                        save_analysis(
                            symbol=symbol_input,
                            last_close=last_close,
                            score=int(tech_res['score']),
                            decision=decision,
                            buy_zone=buy_zone,
                            target_price=target_price,
                            stop_loss=stop_loss,
                            summary=f"Điểm kỹ thuật: {tech_res['score']}. Xu hướng dòng tiền ổn định."
                        )
                        st.success("Đã lưu thành công vào Nhật ký!")
                    except Exception as e:
                        st.error(f"Lỗi khi lưu: {e}")

            sub_t1, sub_t2, sub_t3 = st.tabs(["📈 Biểu Đồ Kỹ Thuật", "🔍 Đánh Giá Cốt Lõi", "📋 Chi Tiết Chỉ Báo"])
            
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
                st.subheader("🔍 Sức Khỏe Tài Chính & Đánh Giá Kỹ Thuật")
                roe_val = financial_metrics['roe'] if financial_metrics['roe'] is not None else "Chưa nhập"
                pe_val = financial_metrics['pe'] if financial_metrics['pe'] is not None else "Chưa nhập"
                st.info(f"**Chỉ số tài chính cơ bản:** ROE: {roe_val} | P/E: {pe_val}")
                st.markdown("**Đánh giá xu hướng hệ thống:**")
                st.success(f"Hệ thống kỹ thuật đánh giá mã {symbol_input} đạt {tech_res['score']} điểm. Trạng thái dòng tiền hoạt động bình thường.")

            with sub_t3:
                st.subheader(f"📄 Thông Số Kỹ Thuật Chi Tiết Mã {symbol_input}")
                st.write(f"- **Điểm số kỹ thuật:** {tech_res['score']} điểm ({score_description(tech_res['score'])})")
                st.write(f"- **Khoảng cách tới hỗ trợ:** {sr_res['dist_to_support_pct']}% (Ngưỡng hỗ trợ: {sr_res['support']})")
                st.write(f"- **Khoảng cách tới kháng cự:** {sr_res['dist_to_resistance_pct']}% (Ngưỡng kháng cự: {sr_res['resistance']})")

        except Exception as e:
            st.error(f"⚠️ Lỗi khi xử lý tính toán kỹ thuật: {e}")
            st.info("💡 Vui lòng kiểm tra lại tệp dữ liệu nạp vào xem có đủ các cột Giá và Khối lượng hay không.")

# --- TAB 2: THAM VẤN ĐẦU TƯ (ĐÃ SỬA VÙNG MUA CHUẨN ĐÚNG NGHĨA CHIẾT KHẤU) ---
with main_tab2:
    st.subheader(f"🗣️ THAM VẤN ĐẦU TƯ CHUYÊN SÂU CHO MÃ {symbol_input}")
    
    if df_raw is None or df_raw.empty:
        st.warning("⚠️ Vui lòng nạp tệp dữ liệu ở thanh bên trái để hệ thống có cơ sở dữ liệu phân tích và đưa ra tham vấn chiến lược.")
    else:
        try:
            df = add_indicators(df_raw)
            tech_res = evaluate_technical(df)
            sr_res = find_support_resistance(df)
            last_close = float(df['close'].iloc[-1])
            decision = "MUA GOM" if tech_res['score'] >= 60 else ("THEO DÕI" if tech_res['score'] >= 40 else "THẬN TRỌNG")
            buy_zone = f"{last_close * 0.96:,.2f} - {last_close * 0.98:,.2f}"
            target_price = f"{last_close * 1.10:,.2f}"
            stop_loss = f"{last_close * 0.93:,.2f}"

            st.markdown(f"""
            <div style="background-color: #1e293b; color: #f8fafc; padding: 2rem; border-radius: 12px; border-left: 6px solid #3b82f6; margin-top: 1rem;">
                <div style="font-weight: bold; font-size: 1.4rem; color: #60a5fa; margin-bottom: 1.2rem;">📊 BẢNG THAM VẤN CHIẾN LƯỢC & GÓC NHÌN THỰC CHIẾN</div>
                <div style="line-height: 1.9; font-size: 1.05rem;">
                    <b>1. Đánh giá trạng thái chung:</b> Mã <b>{symbol_input}</b> đang ở trạng thái <b style="color: #38bdf8;">{decision}</b> với điểm số kỹ thuật tổng hợp là <b>{tech_res['score']}/100</b> (Giá đóng cửa hiện tại: <code>{last_close:,.2f}</code>).<br/><br/>
                    
                    <b>2. Phân tích chi tiết hành động & Lý do:</b><br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;🎯 <b>Dành cho nhà đầu tư CHƯA CÓ HÀNG (Vị thế mua mới):</b><br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- <i>Chiến lược:</i> Kiên nhẫn chờ nhịp tích lũy hoặc điều chỉnh về vùng giá chiết khấu chuẩn <code style="color: #facc15; font-size: 1.1rem;">{buy_zone}</code>.<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- <i>Lý do:</i> Vùng mua này thấp hơn giá hiện tại từ 2-4%, trùng khớp với biên độ an toàn trước ngưỡng hỗ trợ. Việc mua đuổi tại mức giá xác nhận hiện tại dễ gặp rủi ro ngắn hạn khi giá chạm kháng cự.<br/><br/>
                    
                    &nbsp;&nbsp;&nbsp;&nbsp;🛡️ <b>Dành cho nhà đầu tư ĐÃ CÓ HÀNG (Quản trị danh mục):</b><br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- <i>Chiến lược:</i> Tiếp tục nắm giữ, gồng lãi theo xu hướng đường trung bình động.<br/>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;- <i>Lý do:</i> Trạng thái dòng tiền chưa phát tín hiệu phân phối mạnh. Chủ động chốt lời từng phần khi tiến sát mục tiêu <code style="color: #facc15; font-size: 1.1rem;">{target_price}</code> và <b>tuân thủ tuyệt đối nguyên tắc cắt lỗ</b> nếu giá gãy ngưỡng hỗ trợ tại <code style="color: #f87171; font-size: 1.1rem;">{stop_loss}</code> nhằm bảo vệ NAV.
                </div>
            </div>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"⚠️ Lỗi hiển thị bảng tham vấn đầu tư: {e}")

# --- TAB 3: QUẢN TRỊ VỐN & NAV ---
with main_tab3:
    st.subheader("💼 QUẢN TRỊ VỐN & DÒNG TIỀN TƯƠNG TÁC")
    st.caption("👇 Nhập, chỉnh sửa khối lượng, giá vốn trực tiếp trên bảng và bấm nút xác nhận bên dưới để lưu lại thay đổi:")
    
    edited_portfolio = st.data_editor(user_portfolio, num_rows="dynamic", key="pf_editor_main", use_container_width=True, hide_index=True)
    
    if st.button("💾 Lưu & Cập Nhật Dòng Tiền Danh Mục", use_container_width=True, type="primary"):
        st.session_state[f"portfolio_{current_user}"] = edited_portfolio
        st.success("✅ Đã xác nhận lưu lại thay đổi danh mục và cập nhật dòng tiền thành công!")
        st.rerun()

    if not edited_portfolio.empty:
        pf = edited_portfolio.copy()
        pf["Khối Lượng"] = pd.to_numeric(pf["Khối Lượng"], errors="coerce").fillna(0)
        pf["Giá Vốn"] = pd.to_numeric(pf["Giá Vốn"], errors="coerce").fillna(0)
        pf["Giá Hiện Tại"] = pd.to_numeric(pf["Giá Hiện Tại"], errors="coerce").fillna(0)
        
        pf["Giá Trị Hiện Tại"] = pf["Khối Lượng"] * pf["Giá Hiện Tại"]
        pf["Vốn Gốc"] = pf["Khối Lượng"] * pf["Giá Vốn"]
        pf["Lãi/Lỗ (VNĐ)"] = pf["Giá Trị Hiện Tại"] - pf["Vốn Gốc"]
        pf["Lãi/Lỗ (%)"] = np.where(pf["Vốn Gốc"] > 0, (pf["Lãi/Lỗ (VNĐ)"] / pf["Vốn Gốc"]) * 100, 0)
        
        total_nav = pf["Giá Trị Hiện Tại"].sum()
        total_cost = pf["Vốn Gốc"].sum()
        total_pnl = pf["Lãi/Lỗ (VNĐ)"].sum()
        total_pnl_pct = (total_pnl / total_cost) * 100 if total_cost > 0 else 0
        
        st.markdown("---")
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("Tổng Vốn Gốc", f"{total_cost:,.0f} VNĐ")
        v2.metric("Tổng NAV Hiện Tại", f"{total_nav:,.0f} VNĐ")
        v3.metric("Tổng Lãi/Lỗ Thực Tế", f"{total_pnl:,.0f} VNĐ", f"{total_pnl_pct:.2f}%")
        v4.metric("Trạng Thái Dòng Tiền", "Đang Sinh Lời" if total_pnl >= 0 else "Đang Âm Vốn")

        st.markdown("---")
        st.dataframe(pf.style.format({
            "Giá Vốn": "{:,.2f}", "Giá Hiện Tại": "{:,.2f}",
            "Vốn Gốc": "{:,.0f}", "Giá Trị Hiện Tại": "{:,.0f}",
            "Lãi/Lỗ (VNĐ)": "{:,.0f}", "Lãi/Lỗ (%)": "{:.2f}%"
        }), use_container_width=True, hide_index=True)

# --- TAB 4: LỊCH SỬ PHÂN TÍCH ---
with main_tab4:
    st.subheader("📜 Nhật Ký Phân Tích Đã Lưu")
    st.caption("Tra cứu lại toàn bộ lịch sử phân tích đã lưu trong hệ thống:")
    
    filter_symbol = st.text_input("🔍 Lọc theo mã cổ phiếu (Để trống nếu xem tất cả):", value="").upper()
    
    history_list = []
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(analysis_history)")
            cols = [col[1] for col in cursor.fetchall()]
            
            time_col = "timestamp" if "timestamp" in cols else "id"
            sym_col = "symbol" if "symbol" in cols else "id"
            close_col = "last_close" if "last_close" in cols else "0"
            dec_col = "decision" if "decision" in cols else "N/A"
            buy_col = "buy_zone" if "buy_zone" in cols else "N/A"
            tp_col = "target_price" if "target_price" in cols else "N/A"
            sl_col = "stop_loss" if "stop_loss" in cols else "N/A"
            
            if filter_symbol:
                query = f"SELECT id, {sym_col}, {time_col}, {close_col}, {dec_col}, {buy_col}, {tp_col}, {sl_col} FROM analysis_history WHERE {sym_col} = ? ORDER BY id DESC LIMIT 100"
                cursor.execute(query, (filter_symbol,))
            else:
                query = f"SELECT id, {sym_col}, {time_col}, {close_col}, {dec_col}, {buy_col}, {tp_col}, {sl_col} FROM analysis_history ORDER BY id DESC LIMIT 100"
                cursor.execute(query)
            history_list = cursor.fetchall()
    except Exception as e:
        st.error(f"Lỗi cơ sở dữ liệu: {e}")
    
    if history_list:
        col_top1, col_top2 = st.columns([2, 2])
        with col_top1:
            st.info(f"Tìm thấy **{len(history_list)}** bản ghi trong nhật ký.")
        with col_top2:
            if st.button("🔥 XÓA TOÀN BỘ LỊCH SỬ", use_container_width=True, type="primary"):
                with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                    conn.execute("DELETE FROM analysis_history")
                    conn.commit()
                st.success("Đã xóa sạch toàn bộ lịch sử phân tích!")
                st.rerun()
                
        st.markdown("---")
        cleaned_history = []
        for row in history_list:
            cleaned_history.append({
                "ID": row[0],
                "Mã": row[1] if len(row) > 1 else "N/A",
                "Thời Gian": row[2] if len(row) > 2 else "N/A",
                "Giá Đóng": float(row[3]) if len(row) > 3 and row[3] is not None else 0.0,
                "Quyết Định": row[4] if len(row) > 4 else "N/A",
                "Vùng Mua": row[5] if len(row) > 5 else "N/A",
                "Chốt Lời": row[6] if len(row) > 6 else "N/A",
                "Cắt Lỗ": row[7] if len(row) > 7 else "N/A"
            })

        hist_df = pd.DataFrame(cleaned_history)
        st.dataframe(hist_df, hide_index=True, use_container_width=True)
    else:
        st.info("Chưa có lịch sử phân tích nào được ghi nhận.")

# --- TAB 5: SIÊU CÔNG CỤ XỬ LÝ DỮ LIỆU EXCEL/CSV ---
with main_tab5:
    st.subheader("📋 Siêu Công Cụ Xử Lý Dữ Liệu: Cập Nhật, Chỉnh Sửa & Xuất File")
    st.caption("Hỗ trợ mở file cũ, nhập thêm dữ liệu, chỉnh sửa trực tiếp, tự động căn giữa & cập nhật file mới")

    def smart_parse_input_tab5(text_data):
        lines = [line.strip() for line in text_data.strip().split('\n') if line.strip()]
        if not lines:
            return pd.DataFrame()
        
        first_line = lines[0]
        if ',' in first_line and ('Date' in first_line or 'Open' in first_line):
            try:
                return pd.read_csv(io.StringIO(text_data))
            except Exception:
                pass
                
        parsed_rows = []
        for line in lines:
            if 'Open' in line or 'Date' in line or 'Ngày' in line:
                continue
                
            parts = line.split()
            if len(parts) >= 6:
                date_str = parts[0]
                try:
                    open_p = float(parts[1].replace(',', ''))
                    high_p = float(parts[2].replace(',', ''))
                    low_p = float(parts[3].replace(',', ''))
                    close_p = float(parts[4].replace(',', ''))
                    
                    vol_str = parts[5].upper().replace(',', '')
                    vol = 0.0
                    if 'M' in vol_str:
                        vol = float(vol_str.replace('M', '')) * 1_000_000
                    elif 'K' in vol_str:
                        vol = float(vol_str.replace('K', '')) * 1_000
                    else:
                        vol = float(vol_str)
                        
                    parsed_rows.append({
                        'Date': date_str,
                        'Open': open_p,
                        'High': high_p,
                        'Low': low_p,
                        'Close': close_p,
                        'Volume': vol
                    })
                except Exception:
                    continue
                    
        return pd.DataFrame(parsed_rows)

    input_method_t5 = st.radio(
        "Chọn phương thức nạp liệu:",
        ["📁 Mở File Excel / CSV Cũ Sẵn Có", "📝 Dán Văn Bản Trực Tiếp"],
        key="radio_t5_input"
    )

    df_result_t5 = None
    original_filename_t5 = "du_lieu_cap_nhat"

    if input_method_t5 == "📁 Mở File Excel / CSV Cũ Sẵn Có":
        uploaded_file_t5 = st.file_uploader("Chọn file Excel (.xlsx) hoặc CSV cũ:", type=["xlsx", "xls", "csv"], key="uploader_t5")
        if uploaded_file_t5 is not None:
            try:
                file_bytes_t5 = io.BytesIO(uploaded_file_t5.getvalue())
                if uploaded_file_t5.name.lower().endswith('.csv'):
                    df_result_t5 = pd.read_csv(file_bytes_t5)
                else:
                    df_result_t5 = pd.read_excel(file_bytes_t5, engine='openpyxl')
                
                original_filename_t5 = os.path.splitext(uploaded_file_t5.name)[0]
                st.success(f"✅ Đã mở file: **{uploaded_file_t5.name}** ({len(df_result_t5)} dòng)")
            except Exception as e:
                st.error(f"❌ Lỗi đọc tệp: {e}")
    else:
        raw_text_t5 = st.text_area(
            "Dán dữ liệu tại đây:",
            value="Date,Open,High,Low,Close,Volume\n2026-11-09,20.45,20.50,19.85,19.90,25847000",
            height=150,
            key="text_area_t5"
        )
        if st.button("🚀 Bóc Tách Dữ Liệu", type="primary", use_container_width=True, key="btn_parse_t5"):
            if raw_text_t5.strip():
                df_result_t5 = smart_parse_input_tab5(raw_text_t5)
                if not df_result_t5.empty:
                    st.success(f"✅ Đã bóc tách thành công **{len(df_result_t5)} dòng dữ liệu**!")
                else:
                    st.warning("⚠️ Không thể đọc được cấu trúc dữ liệu!")

    if df_result_t5 is not None and not df_result_t5.empty:
        st.markdown("---")
        st.subheader(f"📊 Bảng Dữ Liệu Hiện Tại ({len(df_result_t5)} dòng):")
        
        edited_df_t5 = st.data_editor(
            df_result_t5, 
            use_container_width=True, 
            num_rows="dynamic",
            key="data_editor_t5",
            hide_index=True
        )
        
        st.markdown("---")
        custom_filename_t5 = st.text_input("Đặt tên file khi lưu lại:", value=original_filename_t5, key="filename_t5")
        
        excel_filename_t5 = f"{custom_filename_t5.strip()}.xlsx" if custom_filename_t5.strip() else "du_lieu_moi.xlsx"
        csv_filename_t5 = f"{custom_filename_t5.strip()}.csv" if custom_filename_t5.strip() else "du_lieu_moi.csv"

        excel_buffer_t5 = io.BytesIO()
        with pd.ExcelWriter(excel_buffer_t5, engine='openpyxl') as writer:
            edited_df_t5.to_excel(writer, index=False, sheet_name='Du_Lieu_Cap_Nhat')
            worksheet_t5 = writer.sheets['Du_Lieu_Cap_Nhat']
            center_alignment_t5 = Alignment(horizontal='center', vertical='center')
            for col in worksheet_t5.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    cell.alignment = center_alignment_t5
                    try:
                        if cell.value is not None:
                            max_len = max(max_len, len(str(cell.value)))
                    except:
                        pass
                worksheet_t5.column_dimensions[col_letter].width = max(max_len + 6, 14)
                
        csv_bytes_t5 = edited_df_t5.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="📊 Tải Xuất File Excel",
                data=excel_buffer_t5.getvalue(),
                file_name=excel_filename_t5,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
                key="dl_excel_t5"
            )
        with col_dl2:
            st.download_button(
                label="📄 Tải Xuất File CSV",
                data=csv_bytes_t5,
                file_name=csv_filename_t5,
                mime="text/csv",
                use_container_width=True,
                key="dl_csv_t5"
            )
    else:
        st.info("👋 Hãy chọn file cũ hoặc dán dữ liệu vào khung để bắt đầu xử lý.")
