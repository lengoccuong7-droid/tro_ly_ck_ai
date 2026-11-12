

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import datetime
import io
import os
import re
import unicodedata

from openpyxl.styles import Alignment

from config import APP_NAME, APP_VERSION, DB_PATH

from modules.indicators import add_indicators
from modules.technical_analysis import evaluate_technical
from modules.money_flow import evaluate_money_flow
from modules.support_resistance import find_support_resistance
from modules.stock_scoring import score_description
from modules.ai_analyzer import run_ai_analysis
from modules import decision_engine
import inspect

st.write("FILE DECISION ENGINE:", decision_engine.__file__)

st.write(
    "FUNCTION SIGNATURE:",
    inspect.signature(decision_engine.make_trading_decision)
)
from modules.database import save_analysis, get_recent_history


# =============================================================================
# 1. CẤU HÌNH HỆ THỐNG
# =============================================================================

st.set_page_config(
    page_title=f"{APP_NAME} ULTIMATE PRO",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

current_user = "trader_pro"
# =============================================================================
# 1. CẤU HÌNH HỆ THỐNG
# =============================================================================

st.set_page_config(
    page_title=f"{APP_NAME} ULTIMATE PRO",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

current_user = "trader_pro"


def init_system_db():
    """Khởi tạo bảng nhật ký nếu chưa tồn tại."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        conn.execute("""
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
        """)
        conn.commit()


init_system_db()


# =============================================================================
# 2. QUẢN LÝ SESSION
# =============================================================================

portfolio_key = f"portfolio_{current_user}"

if portfolio_key not in st.session_state:
    st.session_state[portfolio_key] = pd.DataFrame([
        {
            "Mã": "HPG",
            "Khối Lượng": 10000,
            "Giá Vốn": 25.0,
            "Giá Hiện Tại": 27.5
        },
        {
            "Mã": "FPT",
            "Khối Lượng": 5000,
            "Giá Vốn": 49.5,
            "Giá Hiện Tại": 51.0
        }
    ])

user_portfolio = st.session_state[portfolio_key]


# =============================================================================
# 3. CÁC HÀM CHUẨN HÓA DỮ LIỆU
# =============================================================================

def normalize_column_name(name):
    """Chuẩn hóa tên cột, bỏ dấu và ký tự đặc biệt."""

    name = str(name).strip().lower()

    name = unicodedata.normalize("NFD", name)
    name = "".join(
        char for char in name
        if unicodedata.category(char) != "Mn"
    )

    name = name.replace("đ", "d")
    name = re.sub(r"[^a-z0-9]+", " ", name)

    return " ".join(name.split())


COLUMN_ALIASES = {
    "date": [
        "date",
        "time",
        "datetime",
        "trading date",
        "ngay",
        "ngay giao dich",
        "thoi gian",
        "ngay thang",
        "ngay GD"
    ],

    "open": [
        "open",
        "opening price",
        "gia mo",
        "gia mo cua",
        "mo cua",
        "gia mo phien",
        "o"
    ],

    "high": [
        "high",
        "highest",
        "highest price",
        "gia cao",
        "gia cao nhat",
        "cao nhat",
        "h"
    ],

    "low": [
        "low",
        "lowest",
        "lowest price",
        "gia thap",
        "gia thap nhat",
        "thap nhat",
        "l"
    ],

    "close": [
        "close",
        "closing price",
        "last",
        "last price",
        "gia dong",
        "gia dong cua",
        "dong cua",
        "lan cuoi",
        "gia",
        "c"
    ],

    "volume": [
        "volume",
        "vol",
        "trading volume",
        "khoi luong",
        "khoi luong giao dich",
        "kl",
        "v"
    ],

    "pct_change": [
        "change",
        "pct change",
        "change percent",
        "percent change",
        "thay doi",
        "phan tram thay doi",
        "bien dong",
        "thay doi phan tram"
    ]
}


def parse_number(value):
    """
    Chuyển dữ liệu số về float.

    Hỗ trợ:
    - 1,234.56
    - 1.234,56
    - 1234,56
    - 1234.56
    - 25K, 2.5M
    """

    if pd.isna(value):
        return np.nan

    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    text_value = str(value).strip().upper()

    if text_value in ["", "-", "--", "N/A", "NA", "NULL", "NAN"]:
        return np.nan

    text_value = (
        text_value
        .replace("VNĐ", "")
        .replace("VND", "")
        .replace("₫", "")
        .replace(" ", "")
        .replace("%", "")
        .replace("+", "")
    )

    negative = False

    if text_value.startswith("(") and text_value.endswith(")"):
        negative = True
        text_value = text_value[1:-1]

    multiplier = 1.0

    if text_value.endswith("K"):
        multiplier = 1_000
        text_value = text_value[:-1]

    elif text_value.endswith("M"):
        multiplier = 1_000_000
        text_value = text_value[:-1]

    elif text_value.endswith("B"):
        multiplier = 1_000_000_000
        text_value = text_value[:-1]

    if "," in text_value and "." in text_value:

        if text_value.rfind(",") > text_value.rfind("."):
            text_value = text_value.replace(".", "")
            text_value = text_value.replace(",", ".")

        else:
            text_value = text_value.replace(",", "")

    elif "," in text_value:

        parts = text_value.split(",")

        if len(parts) == 2 and len(parts[1]) == 3:
            text_value = text_value.replace(",", "")
        else:
            text_value = text_value.replace(",", ".")

    elif "." in text_value:

        parts = text_value.split(".")

        if len(parts) == 2 and len(parts[1]) == 3:
            text_value = text_value.replace(".", "")

    try:
        result = float(text_value) * multiplier

        if negative:
            result = -result

        return result

    except (ValueError, TypeError):
        return np.nan


def parse_volume(value):
    """Chuyển khối lượng K/M/B về số lượng cổ phiếu."""

    result = parse_number(value)

    if pd.isna(result):
        return 0.0

    return max(float(result), 0.0)


def read_csv_safely(file_bytes):
    """Đọc CSV với nhiều kiểu mã hóa."""

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1258",
        "latin1"
    ]

    last_error = None

    for encoding in encodings:
        try:
            df = pd.read_csv(
                io.BytesIO(file_bytes),
                sep=None,
                engine="python",
                encoding=encoding
            )

            if df.shape[1] > 1:
                return df

        except Exception as error:
            last_error = error

    for separator in [",", ";", "\t", "|"]:

        try:
            df = pd.read_csv(
                io.BytesIO(file_bytes),
                sep=separator,
                encoding="utf-8-sig"
            )

            if df.shape[1] > 1:
                return df

        except Exception as error:
            last_error = error

    raise ValueError(
        f"Không đọc được CSV. Chi tiết: {last_error}"
    )


def read_excel_safely(file_bytes, filename):
    """Đọc Excel xlsx hoặc xls."""

    filename = filename.lower()

    if filename.endswith(".xlsx"):
        return pd.read_excel(
            io.BytesIO(file_bytes),
            engine="openpyxl"
        )

    if filename.endswith(".xls"):

        try:
            return pd.read_excel(
                io.BytesIO(file_bytes),
                engine="xlrd"
            )

        except ImportError:
            raise ValueError(
                "Đọc file .xls cần cài thư viện xlrd. "
                "Bạn có thể chuyển file sang .xlsx."
            )

    raise ValueError("Định dạng Excel không được hỗ trợ.")


def standardize_stock_columns(data):
    """Đổi tên cột dữ liệu về cấu trúc chuẩn."""

    data = data.copy()

    rename_map = {}

    normalized_aliases = {
        standard_name: [
            normalize_column_name(alias)
            for alias in aliases
        ]
        for standard_name, aliases in COLUMN_ALIASES.items()
    }

    for original_column in data.columns:

        normalized_column = normalize_column_name(original_column)

        for standard_name, aliases in normalized_aliases.items():

            if normalized_column in aliases:
                rename_map[original_column] = standard_name
                break

    data = data.rename(columns=rename_map)

    data = data.loc[:, ~data.columns.duplicated()]

    return data


def parse_stock_dates(series):
    """Chuẩn hóa ngày giao dịch."""

    if pd.api.types.is_numeric_dtype(series):

        return pd.to_datetime(
            series,
            unit="D",
            origin="1899-12-30",
            errors="coerce"
        )

    return pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=True
    )


def normalize_stock_data(data):
    """Chuẩn hóa toàn bộ dữ liệu OHLCV."""

    data = standardize_stock_columns(data)

    required_columns = [
        "date",
        "open",
        "high",
        "low",
        "close"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            "Thiếu cột bắt buộc: "
            + ", ".join(missing_columns)
        )

    data["date"] = parse_stock_dates(data["date"])

    for column in ["open", "high", "low", "close"]:
        data[column] = data[column].apply(parse_number)

    if "volume" in data.columns:
        data["volume"] = data["volume"].apply(parse_volume)
    else:
        data["volume"] = 0.0

    if "pct_change" in data.columns:
        data["pct_change"] = data["pct_change"].apply(parse_number)

    data = data.dropna(
        subset=[
            "date",
            "open",
            "high",
            "low",
            "close"
        ]
    )

    # Giá phải lớn hơn 0
    for column in ["open", "high", "low", "close"]:
        data = data[data[column] > 0]

    # Kiểm tra cấu trúc giá OHLC
    invalid_rows = (
        (data["high"] < data["low"])
        | (data["high"] < data["open"])
        | (data["high"] < data["close"])
        | (data["low"] > data["open"])
        | (data["low"] > data["close"])
    )

    invalid_count = int(invalid_rows.sum())

    data = data.loc[~invalid_rows].copy()

    data["volume"] = pd.to_numeric(
        data["volume"],
        errors="coerce"
    ).fillna(0).clip(lower=0)

    data = (
        data
        .sort_values("date")
        .drop_duplicates(
            subset=["date"],
            keep="last"
        )
        .reset_index(drop=True)
    )

    if data.empty:
        raise ValueError(
            "Không còn dữ liệu hợp lệ sau khi chuẩn hóa."
        )

    return data, invalid_count


# =============================================================================
# 4. ĐỌC DỮ LIỆU CỔ PHIẾU
# =============================================================================

st.title(f"📈 {APP_NAME} (v{APP_VERSION} ULTIMATE PRO)")
st.caption(
    f"Hệ thống Phân tích Chứng khoán Thực chiến | "
    f"Tài khoản: **{current_user}**"
)

st.sidebar.header("⚙️ 1. Nguồn Dữ Liệu Lịch Sử")

uploaded_file = st.sidebar.file_uploader(
    "Nạp tệp CSV hoặc Excel",
    type=["csv", "xlsx", "xls"],
    key="main_stock_data_uploader"
)

df_raw = None

if uploaded_file is not None:

    try:
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name.lower()

        if filename.endswith(".csv"):
            imported_data = read_csv_safely(file_bytes)

        else:
            imported_data = read_excel_safely(
                file_bytes,
                filename
            )

        df_raw, invalid_count = normalize_stock_data(
            imported_data
        )

        st.sidebar.success(
            f"✅ Nạp thành công {len(df_raw)} phiên dữ liệu."
        )

        st.sidebar.caption(
            f"Ngày đầu: {df_raw['date'].min():%d/%m/%Y}"
        )

        st.sidebar.caption(
            f"Ngày cuối: {df_raw['date'].max():%d/%m/%Y}"
        )

        st.sidebar.caption(
            f"Giá đóng cửa gần nhất: "
            f"{df_raw['close'].iloc[-1]:,.2f}"
        )

        if invalid_count > 0:
            st.sidebar.warning(
                f"Đã loại bỏ {invalid_count} dòng có cấu trúc giá bất thường."
            )

        if len(df_raw) < 60:
            st.sidebar.warning(
                "Dữ liệu dưới 60 phiên. "
                "Một số chỉ báo dài hạn có thể chưa đủ dữ liệu."
            )

        if (df_raw["volume"] == 0).all():
            st.sidebar.warning(
                "Khối lượng đang bằng 0 hoặc không có dữ liệu. "
                "Phân tích dòng tiền có thể không chính xác."
            )

    except Exception as error:
        df_raw = None

        st.sidebar.error(
            f"❌ Lỗi nạp dữ liệu: {error}"
        )


symbol_input = st.sidebar.text_input(
    "Mã cổ phiếu phân tích",
    value="FPT"
).strip().upper()


# =============================================================================
# 5. DỮ LIỆU ATO
# =============================================================================

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 2. Cập Nhật Giá Đầu Phiên (ATO)")

col_a1, col_a2 = st.sidebar.columns(2)

with col_a1:
    ato_open_in = st.text_input(
        "Giá ATO",
        value=""
    )

with col_a2:
    ato_vol_in = st.text_input(
        "KL ATO",
        value=""
    )


ato_data = {
    "open": None,
    "volume": None
}

if ato_open_in.strip():
    ato_data["open"] = parse_number(ato_open_in)

if ato_vol_in.strip():
    ato_data["volume"] = parse_volume(ato_vol_in)


# =============================================================================
# 6. DỮ LIỆU TÀI CHÍNH CƠ BẢN
# =============================================================================

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 3. Báo Cáo Tài Chính Cơ Bản")

fin_roe = st.sidebar.text_input("ROE (%)", value="")
fin_pe = st.sidebar.text_input("P/E", value="")
fin_debt = st.sidebar.text_input("Nợ/VCSH", value="")

financial_metrics = {
    "roe": parse_number(fin_roe) if fin_roe.strip() else None,
    "pe": parse_number(fin_pe) if fin_pe.strip() else None,
    "debt_equity": parse_number(fin_debt) if fin_debt.strip() else None
}


# =============================================================================
# 7. HÀM PHÂN TÍCH TẬP TRUNG
# =============================================================================

@st.cache_data(show_spinner=False)
def calculate_stock_analysis(data, symbol, ato_data=None, financial_metrics=None):
    """Phan tich tap trung: tinh mot lan va dung chung cho TAB 1/TAB 2."""
    df = add_indicators(data.copy())

    ai_res = run_ai_analysis(
        df=df,
        symbol=symbol,
        ato_data=ato_data,
        financial_metrics=financial_metrics,
    )

    decision_res = decision_engine.make_trading_decision(
        df=df,
        ai_result=ai_res,
        capital_vnd=100_000_000,
        risk_per_trade_pct=1.0,
        max_allocation_pct=20.0,
        price_multiplier=1_000.0,
        lot_size=100,
    )

    tech_res = evaluate_technical(df)
    flow_res = evaluate_money_flow(df)
    sr_res = find_support_resistance(df)
    last_close = float(df["close"].iloc[-1])

    return {
        "df": df,
        "tech": tech_res,
        "flow": flow_res,
        "support_resistance": sr_res,
        "ai": ai_res,
        "decision_detail": decision_res,
        "last_close": last_close,
        # Luu diem quy doi 0-100 vao nhat ky de hien thi dung thang diem.
        "score": decision_res["score_100"],
        "technical_score_raw": decision_res["technical_score_raw"],
        "decision": decision_res["decision"],
        "buy_zone": decision_res["buy_zone"],
        "target_price": decision_res["target_price"],
        "stop_loss": decision_res["stop_loss"],
        "confirm_price": decision_res["confirm_price"],
    }


analysis = None
analysis_error = None

if df_raw is not None and not df_raw.empty:

    try:
        analysis = calculate_stock_analysis(
            df_raw, symbol_input, ato_data, financial_metrics
        )

    except Exception as error:
        analysis_error = str(error)


# =============================================================================
# 8. TẠO 5 TAB CHÍNH
# =============================================================================

main_tab1, main_tab2, main_tab3, main_tab4, main_tab5 = st.tabs([
    "📊 TAB 1: KỸ THUẬT & TÀI CHÍNH",
    "🗣️ TAB 2: THAM VẤN ĐẦU TƯ",
    "💼 TAB 3: QUẢN TRỊ VỐN & NAV",
    "📜 TAB 4: LỊCH SỬ PHÂN TÍCH",
    "📋 TAB 5: XỬ LÝ DỮ LIỆU EXCEL/CSV"
])


# =============================================================================
# TAB 1: KỸ THUẬT & TÀI CHÍNH
# =============================================================================

with main_tab1:

    if df_raw is None or df_raw.empty:

        st.warning(
            "⚠️ CHƯA CÓ DỮ LIỆU LỊCH SỬ. "
            "Vui lòng tải file CSV/Excel ở thanh bên trái."
        )

    elif analysis_error:

        st.error(
            f"Lỗi khi xử lý phân tích: {analysis_error}"
        )

    else:

        df = analysis["df"]
        tech_res = analysis["tech"]
        flow_res = analysis["flow"]
        sr_res = analysis["support_resistance"]

        last_close = analysis["last_close"]
        score = analysis["score"]
        technical_score_raw = analysis["technical_score_raw"]
        decision_detail = analysis["decision_detail"]
        ai_res = analysis["ai"]
        decision = analysis["decision"]

        buy_zone = analysis["buy_zone"]
        target_price = analysis["target_price"]
        stop_loss = analysis["stop_loss"]

        st.subheader(
            f"🎯 TÍN HIỆU & VÙNG GIAO DỊCH MÃ {symbol_input}"
        )

        m1, m2, m3, m4, m5 = st.columns(5)

        m1.metric("QUYẾT ĐỊNH", decision)
        m2.metric("VÙNG MUA", buy_zone)
        m3.metric("GIÁ XÁC NHẬN", f"{last_close:,.2f}")
        m4.metric("CHỐT LỜI (TP)", target_price)
        m5.metric("CẮT LỖ (SL)", stop_loss)

        st.info(
            f"**Xu hướng:** {decision_detail['trend']} | "
            f"**Động lượng:** {decision_detail['momentum']} | "
            f"**Dòng tiền:** {decision_detail['flow_status']}"
        )
        st.write(f"**Lý do khuyến nghị:** {decision_detail['reason']}")
        st.write(
            f"**Hành động nếu đang nắm giữ:** {decision_detail['holding_action']}"
        )
        st.caption(
            f"Tỷ lệ LN/RR tham khảo: {decision_detail['reward_risk']:.2f}R | "
            f"Khối lượng tối đa theo quản trị rủi ro: "
            f"{decision_detail['suggested_quantity']:,} cổ phiếu | "
            f"Giá trị dự kiến: {decision_detail['estimated_position_value_vnd']:,.0f} VNĐ | "
            f"Lỗ dự kiến tại stop: {decision_detail['estimated_loss_at_stop_vnd']:,.0f} VNĐ"
        )
        if decision_detail["warnings"]:
            with st.expander("Cảnh báo và điều kiện cần kiểm tra"):
                for warning in decision_detail["warnings"]:
                    st.write(f"- {warning}")

        st.markdown("---")

        col_save1, col_save2 = st.columns([3, 1])

        with col_save1:
            st.info(
                f"Bấm nút bên phải để lưu kết quả phân tích "
                f"mã **{symbol_input}** vào Nhật ký."
            )

        with col_save2:

            if st.button(
                "💾 Lưu Phân Tích Này",
                use_container_width=True,
                type="primary"
            ):

                try:

                    save_analysis(
                        symbol=symbol_input,
                        last_close=last_close,
                        score=score,
                        decision=decision,
                        buy_zone=buy_zone,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        summary=(
                            f"Điểm kỹ thuật: {score}. "
                            f"Trạng thái: {decision}."
                        )
                    )

                    st.success(
                        "Đã lưu thành công vào Nhật ký!"
                    )

                except Exception as error:

                    st.error(
                        f"Lỗi khi lưu: {error}"
                    )

        sub_t1, sub_t2, sub_t3 = st.tabs([
            "📈 Biểu Đồ Kỹ Thuật",
            "🔍 Đánh Giá Cốt Lõi",
            "📋 Chi Tiết Chỉ Báo"
        ])

        # ---------------------------------------------------------------------
        # BIỂU ĐỒ
        # ---------------------------------------------------------------------

        with sub_t1:

            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3]
            )

            fig.add_trace(
                go.Candlestick(
                    x=df["date"],
                    open=df["open"],
                    high=df["high"],
                    low=df["low"],
                    close=df["close"],
                    name="Giá"
                ),
                row=1,
                col=1
            )

            if "MA20" in df.columns:

                fig.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=df["MA20"],
                        name="MA20",
                        line=dict(color="orange", width=1)
                    ),
                    row=1,
                    col=1
                )

            if "MA50" in df.columns:

                fig.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=df["MA50"],
                        name="MA50",
                        line=dict(color="blue", width=1)
                    ),
                    row=1,
                    col=1
                )

            if "volume" in df.columns:

                colors = [
                    "green" if df["close"].iloc[i] >= df["open"].iloc[i]
                    else "red"
                    for i in range(len(df))
                ]

                fig.add_trace(
                    go.Bar(
                        x=df["date"],
                        y=df["volume"],
                        name="Khối lượng",
                        marker_color=colors
                    ),
                    row=2,
                    col=1
                )

            fig.update_layout(
                title=f"Biểu đồ kỹ thuật mã {symbol_input}",
                xaxis_rangeslider_visible=False,
                height=480
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        # ---------------------------------------------------------------------
        # ĐÁNH GIÁ CỐT LÕI
        # ---------------------------------------------------------------------

        with sub_t2:

            st.subheader(
                "🔍 SỨC KHỎE TÀI CHÍNH & ĐÁNH GIÁ KỸ THUẬT"
            )

            roe_val = (
                financial_metrics["roe"]
                if financial_metrics["roe"] is not None
                else "Chưa nhập"
            )

            pe_val = (
                financial_metrics["pe"]
                if financial_metrics["pe"] is not None
                else "Chưa nhập"
            )

            debt_val = (
                financial_metrics["debt_equity"]
                if financial_metrics["debt_equity"] is not None
                else "Chưa nhập"
            )

            st.info(
                f"ROE: {roe_val} | "
                f"P/E: {pe_val} | "
                f"Nợ/VCSH: {debt_val}"
            )

            st.metric(
                "Điểm tổng hợp kỹ thuật",
                f"{score}/100"
            )
            st.caption(
                f"Điểm gốc của module kỹ thuật: {technical_score_raw:+d} / 6. "
                "Điểm 0-100 là thang quy đổi, không phải xác suất tăng giá."
            )

            st.write(
                f"**Đánh giá:** {score_description(technical_score_raw)}"
            )

            st.write(
                f"**Quyết định:** {decision}"
            )

            st.markdown("---")

            st.subheader("Dòng tiền")

            if isinstance(flow_res, dict):

                for key, value in flow_res.items():

                    st.write(
                        f"**{key}:** {value}"
                    )

            else:

                st.write(flow_res)

            st.caption(
                "Kết quả dòng tiền được lấy từ module money_flow.py."
            )

            st.markdown("---")

            st.subheader("Hỗ trợ và kháng cự")

            st.write(
                f"**Hỗ trợ:** {sr_res.get('support', 'Chưa có dữ liệu')}"
            )

            st.write(
                f"**Kháng cự:** {sr_res.get('resistance', 'Chưa có dữ liệu')}"
            )

            st.write(
                f"**Khoảng cách tới hỗ trợ:** "
                f"{sr_res.get('dist_to_support_pct', 'N/A')}%"
            )

            st.write(
                f"**Khoảng cách tới kháng cự:** "
                f"{sr_res.get('dist_to_resistance_pct', 'N/A')}%"
            )

        # ---------------------------------------------------------------------
        # CHI TIẾT CHỈ BÁO
        # ---------------------------------------------------------------------

        with sub_t3:

            st.subheader(
                f"📄 THÔNG SỐ KỸ THUẬT MÃ {symbol_input}"
            )

            st.write(
                f"- **Điểm tổng hợp kỹ thuật:** {score}/100 (điểm gốc {technical_score_raw:+d}/6)"
            )

            st.write(
                f"- **Đánh giá:** {score_description(technical_score_raw)}"
            )

            st.write(
                f"- **Hỗ trợ:** {sr_res.get('support', 'N/A')}"
            )

            st.write(
                f"- **Kháng cự:** {sr_res.get('resistance', 'N/A')}"
            )

            st.write(
                f"- **Khoảng cách hỗ trợ:** "
                f"{sr_res.get('dist_to_support_pct', 'N/A')}%"
            )

            st.write(
                f"- **Khoảng cách kháng cự:** "
                f"{sr_res.get('dist_to_resistance_pct', 'N/A')}%"
            )

            st.markdown("---")

            st.subheader("Dữ liệu gần nhất")

            st.dataframe(
                df.tail(20),
                use_container_width=True,
                hide_index=True
            )


# =============================================================================
# TAB 2: THAM VẤN ĐẦU TƯ
# =============================================================================

with main_tab2:

    st.subheader(f"🗣️ THAM VẤN ĐẦU TƯ SWING CHO MÃ {symbol_input}")

    if df_raw is None or df_raw.empty:
        st.warning("Vui lòng nạp dữ liệu ở thanh bên trái.")
    elif analysis_error:
        st.error(f"Lỗi phân tích: {analysis_error}")
    else:
        detail = analysis["decision_detail"]
        ai_res = analysis["ai"]
        st.metric("KHUYẾN NGHỊ CHO VỊ THẾ MỚI", detail["decision"])
        st.write(f"**Xu hướng:** {detail['trend']}")
        st.write(f"**Động lượng:** {detail['momentum']}")
        st.write(f"**Dòng tiền:** {detail['flow_status']}")
        st.write(
            f"**Điểm tổng hợp:** {detail['score_100']}/100 "
            f"(điểm kỹ thuật gốc {detail['technical_score_raw']:+d}/6)."
        )
        st.caption("Điểm 0-100 là điểm quy đổi từ bộ chỉ báo, không phải xác suất sinh lời.")

        st.markdown("### 1. Nếu CHƯA có cổ phiếu")
        st.write(f"- **Vùng mua tham khảo:** {detail['buy_zone']}")
        st.write(f"- **Giá hiện tại/giá xác nhận:** {detail['confirm_price']}")
        st.write(f"- **Giá mục tiêu:** {detail['target_price']}")
        st.write(f"- **Giá cắt lỗ:** {detail['stop_loss']}")
        st.write(f"- **Tỷ lệ lợi nhuận/rủi ro:** {detail['reward_risk']:.2f}R")
        st.write(f"- **Lý do:** {detail['reason']}")

        st.markdown("### 2. Nếu ĐANG nắm giữ")
        st.info(detail["holding_action"])

        st.markdown("### 3. Quản trị vốn mẫu 100 triệu đồng")
        c1, c2, c3 = st.columns(3)
        c1.metric("Khối lượng tối đa tham khảo", f"{detail['suggested_quantity']:,} cp")
        c2.metric("Giá trị vị thế", f"{detail['estimated_position_value_vnd']:,.0f} đ")
        c3.metric("Rủi ro tại stop", f"{detail['estimated_loss_at_stop_vnd']:,.0f} đ")
        st.caption(
            "Mô hình giả định giá trong file đang tính theo nghìn đồng/cổ phiếu, "
            "lô giao dịch 100 cổ phiếu, rủi ro tối đa 1% NAV/lệnh và tỷ trọng tối đa 20% NAV. "
            "Nếu dữ liệu giá là VND/cổ phiếu, cần đổi price_multiplier từ 1.000 thành 1."
        )

        st.markdown("### 4. Cảnh báo và luận cứ")
        for item in detail["warnings"]:
            st.warning(item)
        with st.expander("Xem các tín hiệu kỹ thuật chi tiết"):
            for item in detail["technical_signals"]:
                st.write(f"- {item}")
            st.write(f"**ATO:** {ai_res['ato_summary']}")
            st.write(f"**Tài chính:** {ai_res['fin_summary']}")

        st.warning(
            "Đây là bộ lọc và kế hoạch giao dịch tham khảo, chưa được chứng minh hiệu quả "
            "bằng backtest/out-of-sample. Không tự động đặt lệnh và không bảo đảm lợi nhuận."
        )


# =============================================================================
# TAB 3: QUẢN TRỊ VỐN & NAV
# =============================================================================

with main_tab3:

    st.subheader(
        "💼 QUẢN TRỊ VỐN & DÒNG TIỀN"
    )

    st.caption(
        "Nhập và chỉnh sửa danh mục trực tiếp trên bảng."
    )

    edited_portfolio = st.data_editor(
        user_portfolio,
        num_rows="dynamic",
        key="pf_editor_main",
        use_container_width=True,
        hide_index=True
    )

    if st.button(
        "💾 Lưu & Cập Nhật Dòng Tiền Danh Mục",
        use_container_width=True,
        type="primary"
    ):

        st.session_state[portfolio_key] = edited_portfolio

        st.success(
            "Đã lưu danh mục thành công!"
        )

        st.rerun()

    if not edited_portfolio.empty:

        pf = edited_portfolio.copy()

        required_pf_columns = [
            "Mã",
            "Khối Lượng",
            "Giá Vốn",
            "Giá Hiện Tại"
        ]

        missing_pf_columns = [
            col for col in required_pf_columns
            if col not in pf.columns
        ]

        if missing_pf_columns:

            st.error(
                "Thiếu cột danh mục: "
                + ", ".join(missing_pf_columns)
            )

        else:

            for col in [
                "Khối Lượng",
                "Giá Vốn",
                "Giá Hiện Tại"
            ]:

                pf[col] = pd.to_numeric(
                    pf[col],
                    errors="coerce"
                ).fillna(0)

            pf["Giá Trị Hiện Tại"] = (
                pf["Khối Lượng"] * pf["Giá Hiện Tại"]
            )

            pf["Vốn Gốc"] = (
                pf["Khối Lượng"] * pf["Giá Vốn"]
            )

            pf["Lãi/Lỗ (VNĐ)"] = (
                pf["Giá Trị Hiện Tại"] - pf["Vốn Gốc"]
            )

            pf["Lãi/Lỗ (%)"] = np.where(
                pf["Vốn Gốc"] > 0,
                pf["Lãi/Lỗ (VNĐ)"] / pf["Vốn Gốc"] * 100,
                0
            )

            total_nav = pf["Giá Trị Hiện Tại"].sum()
            total_cost = pf["Vốn Gốc"].sum()
            total_pnl = pf["Lãi/Lỗ (VNĐ)"].sum()

            total_pnl_pct = (
                total_pnl / total_cost * 100
                if total_cost > 0
                else 0
            )

            st.markdown("---")

            v1, v2, v3, v4 = st.columns(4)

            v1.metric(
                "Tổng Vốn Gốc",
                f"{total_cost:,.0f} VNĐ"
            )

            v2.metric(
                "Tổng NAV",
                f"{total_nav:,.0f} VNĐ"
            )

            v3.metric(
                "Tổng Lãi/Lỗ",
                f"{total_pnl:,.0f} VNĐ",
                f"{total_pnl_pct:.2f}%"
            )

            v4.metric(
                "Trạng Thái",
                "Đang Sinh Lời"
                if total_pnl >= 0
                else "Đang Âm Vốn"
            )

            st.markdown("---")

            st.dataframe(
                pf.style.format({
                    "Giá Vốn": "{:,.2f}",
                    "Giá Hiện Tại": "{:,.2f}",
                    "Vốn Gốc": "{:,.0f}",
                    "Giá Trị Hiện Tại": "{:,.0f}",
                    "Lãi/Lỗ (VNĐ)": "{:,.0f}",
                    "Lãi/Lỗ (%)": "{:.2f}%"
                }),
                use_container_width=True,
                hide_index=True
            )


# =============================================================================
# TAB 4: LỊCH SỬ PHÂN TÍCH
# =============================================================================

with main_tab4:

    st.subheader(
        "📜 NHẬT KÝ PHÂN TÍCH"
    )

    filter_symbol = st.text_input(
        "🔍 Lọc theo mã cổ phiếu",
        value="",
        key="history_filter_symbol"
    ).strip().upper()

    history_list = []

    try:

        with sqlite3.connect(
            DB_PATH,
            check_same_thread=False
        ) as conn:

            cursor = conn.cursor()

            cursor.execute(
                "PRAGMA table_info(analysis_history)"
            )

            cols = [
                col[1]
                for col in cursor.fetchall()
            ]

            expected_columns = [
                "id",
                "symbol",
                "timestamp",
                "last_close",
                "score",
                "decision",
                "buy_zone",
                "target_price",
                "stop_loss",
                "summary"
            ]

            missing = [
                col
                for col in expected_columns
                if col not in cols
            ]

            if missing:

                st.warning(
                    "Cấu trúc bảng nhật ký hiện tại thiếu: "
                    + ", ".join(missing)
                )

            else:

                if filter_symbol:

                    cursor.execute("""
                        SELECT
                            id,
                            symbol,
                            timestamp,
                            last_close,
                            score,
                            decision,
                            buy_zone,
                            target_price,
                            stop_loss,
                            summary
                        FROM analysis_history
                        WHERE symbol = ?
                        ORDER BY id DESC
                        LIMIT 100
                    """, (filter_symbol,))

                else:

                    cursor.execute("""
                        SELECT
                            id,
                            symbol,
                            timestamp,
                            last_close,
                            score,
                            decision,
                            buy_zone,
                            target_price,
                            stop_loss,
                            summary
                        FROM analysis_history
                        ORDER BY id DESC
                        LIMIT 100
                    """)

                history_list = cursor.fetchall()

    except Exception as error:

        st.error(
            f"Lỗi cơ sở dữ liệu: {error}"
        )

    if history_list:

        col_top1, col_top2 = st.columns([2, 2])

        with col_top1:

            st.info(
                f"Tìm thấy {len(history_list)} bản ghi."
            )

        with col_top2:

            if st.button(
                "🔥 XÓA TOÀN BỘ LỊCH SỬ",
                use_container_width=True,
                type="primary"
            ):

                st.session_state["confirm_delete_history"] = True

        if st.session_state.get("confirm_delete_history", False):

            st.warning(
                "Bạn có chắc chắn muốn xóa toàn bộ lịch sử không?"
            )

            confirm_col1, confirm_col2 = st.columns(2)

            with confirm_col1:

                if st.button(
                    "Xác nhận xóa",
                    type="primary"
                ):

                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute(
                            "DELETE FROM analysis_history"
                        )
                        conn.commit()

                    st.session_state["confirm_delete_history"] = False

                    st.success(
                        "Đã xóa lịch sử."
                    )

                    st.rerun()

            with confirm_col2:

                if st.button("Hủy"):

                    st.session_state["confirm_delete_history"] = False

                    st.rerun()

        cleaned_history = []

        for row in history_list:

            cleaned_history.append({
                "ID": row[0],
                "Mã": row[1],
                "Thời Gian": row[2],
                "Giá Đóng": row[3],
                "Điểm": row[4],
                "Quyết Định": row[5],
                "Vùng Mua": row[6],
                "Chốt Lời": row[7],
                "Cắt Lỗ": row[8],
                "Tóm Tắt": row[9]
            })

        hist_df = pd.DataFrame(cleaned_history)

        st.dataframe(
            hist_df,
            hide_index=True,
            use_container_width=True
        )

    else:

        st.info(
            "Chưa có lịch sử phân tích nào được ghi nhận."
        )


# =============================================================================
# TAB 5: SIÊU CÔNG CỤ XỬ LÝ DỮ LIỆU EXCEL/CSV
# GIỮ NGUYÊN CHỨC NĂNG ĐỘC LẬP
# =============================================================================

with main_tab5:

    st.subheader(
        "📋 Siêu Công Cụ Xử Lý Dữ Liệu: Cập Nhật, Chỉnh Sửa & Xuất File"
    )

    st.caption(
        "Hỗ trợ mở file cũ, nhập thêm dữ liệu, chỉnh sửa trực tiếp, "
        "tự động căn giữa & cập nhật file mới"
    )

    def smart_parse_input_tab5(text_data):

        lines = [
            line.strip()
            for line in text_data.strip().split('\n')
            if line.strip()
        ]

        if not lines:
            return pd.DataFrame()

        first_line = lines[0]

        if ',' in first_line and (
            'Date' in first_line or 'Open' in first_line
        ):

            try:
                return pd.read_csv(
                    io.StringIO(text_data)
                )

            except Exception:
                pass

        parsed_rows = []

        for line in lines:

            if (
                'Open' in line
                or 'Date' in line
                or 'Ngày' in line
            ):
                continue

            parts = line.split()

            if len(parts) >= 6:

                date_str = parts[0]

                try:

                    open_p = float(
                        parts[1].replace(',', '')
                    )

                    high_p = float(
                        parts[2].replace(',', '')
                    )

                    low_p = float(
                        parts[3].replace(',', '')
                    )

                    close_p = float(
                        parts[4].replace(',', '')
                    )

                    vol_str = (
                        parts[5]
                        .upper()
                        .replace(',', '')
                    )

                    vol = 0.0

                    if 'M' in vol_str:

                        vol = (
                            float(vol_str.replace('M', ''))
                            * 1_000_000
                        )

                    elif 'K' in vol_str:

                        vol = (
                            float(vol_str.replace('K', ''))
                            * 1_000
                        )

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
        [
            "📁 Mở File Excel / CSV Cũ Sẵn Có",
            "📝 Dán Văn Bản Trực Tiếp"
        ],
        key="radio_t5_input"
    )

    df_result_t5 = None

    original_filename_t5 = "du_lieu_cap_nhat"

    if input_method_t5 == "📁 Mở File Excel / CSV Cũ Sẵn Có":

        uploaded_file_t5 = st.file_uploader(
            "Chọn file Excel (.xlsx) hoặc CSV cũ:",
            type=["xlsx", "xls", "csv"],
            key="uploader_t5"
        )

        if uploaded_file_t5 is not None:

            try:

                file_bytes_t5 = io.BytesIO(
                    uploaded_file_t5.getvalue()
                )

                if uploaded_file_t5.name.lower().endswith('.csv'):

                    df_result_t5 = pd.read_csv(
                        file_bytes_t5
                    )

                else:

                    df_result_t5 = pd.read_excel(
                        file_bytes_t5,
                        engine='openpyxl'
                    )

                original_filename_t5 = os.path.splitext(
                    uploaded_file_t5.name
                )[0]

                st.success(
                    f"✅ Đã mở file: **{uploaded_file_t5.name}** "
                    f"({len(df_result_t5)} dòng)"
                )

            except Exception as e:

                st.error(
                    f"❌ Lỗi đọc tệp: {e}"
                )

    else:

        raw_text_t5 = st.text_area(
            "Dán dữ liệu tại đây:",
            value=(
                "Date,Open,High,Low,Close,Volume\n"
                "2026-11-09,20.45,20.50,19.85,19.90,25847000"
            ),
            height=150,
            key="text_area_t5"
        )

        if st.button(
            "🚀 Bóc Tách Dữ Liệu",
            type="primary",
            use_container_width=True,
            key="btn_parse_t5"
        ):

            if raw_text_t5.strip():

                df_result_t5 = smart_parse_input_tab5(
                    raw_text_t5
                )

                if not df_result_t5.empty:

                    st.success(
                        f"✅ Đã bóc tách thành công "
                        f"**{len(df_result_t5)} dòng dữ liệu**!"
                    )

                else:

                    st.warning(
                        "⚠️ Không thể đọc được cấu trúc dữ liệu!"
                    )

    if df_result_t5 is not None and not df_result_t5.empty:

        st.markdown("---")

        st.subheader(
            f"📊 Bảng Dữ Liệu Hiện Tại ({len(df_result_t5)} dòng):"
        )

        edited_df_t5 = st.data_editor(
            df_result_t5,
            use_container_width=True,
            num_rows="dynamic",
            key="data_editor_t5",
            hide_index=True
        )

        st.markdown("---")

        custom_filename_t5 = st.text_input(
            "Đặt tên file khi lưu lại:",
            value=original_filename_t5,
            key="filename_t5"
        )

        excel_filename_t5 = (
            f"{custom_filename_t5.strip()}.xlsx"
            if custom_filename_t5.strip()
            else "du_lieu_moi.xlsx"
        )

        csv_filename_t5 = (
            f"{custom_filename_t5.strip()}.csv"
            if custom_filename_t5.strip()
            else "du_lieu_moi.csv"
        )

        excel_buffer_t5 = io.BytesIO()

        with pd.ExcelWriter(
            excel_buffer_t5,
            engine='openpyxl'
        ) as writer:

            edited_df_t5.to_excel(
                writer,
                index=False,
                sheet_name='Du_Lieu_Cap_Nhat'
            )

            worksheet_t5 = writer.sheets[
                'Du_Lieu_Cap_Nhat'
            ]

            center_alignment_t5 = Alignment(
                horizontal='center',
                vertical='center'
            )

            for col in worksheet_t5.columns:

                max_len = 0

                col_letter = col[0].column_letter

                for cell in col:

                    cell.alignment = center_alignment_t5

                    try:

                        if cell.value is not None:

                            max_len = max(
                                max_len,
                                len(str(cell.value))
                            )

                    except:
                        pass

                worksheet_t5.column_dimensions[
                    col_letter
                ].width = max(max_len + 6, 14)

        csv_bytes_t5 = edited_df_t5.to_csv(
            index=False,
            encoding='utf-8-sig'
        ).encode('utf-8-sig')

        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:

            st.download_button(
                label="📊 Tải Xuất File Excel",
                data=excel_buffer_t5.getvalue(),
                file_name=excel_filename_t5,
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
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

        st.info(
            "👋 Hãy chọn file cũ hoặc dán dữ liệu vào khung "
            "để bắt đầu xử lý."
        )


# =============================================================================
#  KẾT THÚC APP
# =============================================================================
