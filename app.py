import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

# --- 1. CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="Riken Viet - Gas Mapping", layout="wide")
st.title("🛡️ Công cụ Thiết kế Vùng phủ Khí & Xuất Báo cáo Tự động")
st.markdown("**Phát triển bởi: Riken Viet - Phòng Kỹ thuật**")

# --- 2. GIAO DIỆN NHẬP LIỆU ---
col_input, col_view = st.columns([1, 1.5])

with col_input:
    st.header("1. Cấu hình Hệ thống")
    with st.expander("Kích thước không gian (m)", expanded=True):
        room_x = st.number_input("Chiều dài (X)", min_value=1.0, value=15.0)
        room_y = st.number_input("Chiều rộng (Y)", min_value=1.0, value=10.0)
        room_z = st.number_input("Chiều cao trần (Z)", min_value=1.0, value=5.0)

    with st.expander("Vật cản (Bồn chứa hình trụ)", expanded=True):
        default_obstacles = pd.DataFrame([
            {"Type": "Cylinder", "X": 7.5, "Y": 5.0, "Radius": 1.5, "Height": 3.5}
        ])
        edited_obs = st.data_editor(default_obstacles, num_rows="dynamic", use_container_width=True)

    with st.expander("Đầu dò khí (Detectors)", expanded=True):
        default_detectors = pd.DataFrame([
            {"ID": "SD-1 (01)", "X": 4.0, "Y": 5.0, "Z": 2.0, "Radius": 5.0, "Color": "Cyan"},
            {"ID": "SD-1 (02)", "X": 11.0, "Y": 5.0, "Z": 2.0, "Radius": 5.0, "Color": "Magenta"}
        ])
        edited_dets = st.data_editor(default_detectors, num_rows="dynamic", use_container_width=True)

# --- 3. LÕI XỬ LÝ (2D MAP & WORD REPORT) ---

def generate_2d_plot(rx, ry, df_obs, df_dets):
    """Tính toán lưới và vẽ biểu đồ 2D bằng Matplotlib"""
    res = 0.1
    xx, yy = np.meshgrid(np.arange(0, rx, res), np.arange(0, ry, res))
    tong_vung_phu = np.zeros_like(xx, dtype=bool)
    khong_gian_trong_bon = np.zeros_like(xx, dtype=bool)

    # Lấy thông số bồn chứa đầu tiên (để đơn giản hóa demo Shadowing)
    bon_chua = None
    if not df_obs.empty:
        obs_row = df_obs.iloc[0]
        bon_chua = {'x': obs_row['X'], 'y': obs_row['Y'], 'r': obs_row['Radius']}
        khong_gian_trong_bon = np.sqrt((xx - bon_chua['x'])**2 + (yy - bon_chua['y'])**2) <= bon_chua['r']

    for _, det in df_dets.iterrows():
        dx, dy, dr = det['X'], det['Y'], det['Radius']
        trong_ban_kinh = np.sqrt((xx - dx)**2 + (yy - dy)**2) <= dr
        
        bi_che_khuat = np.zeros_like(xx, dtype=bool)
        if bon_chua:
            # Thuật toán Line of Sight
            vx, vy = xx - dx, yy - dy
            wx, wy = bon_chua['x'] - dx, bon_chua['y'] - dy
            v_sq = vx**2 + vy**2
            v_sq[v_sq == 0] = 1e-10
            b = (wx * vx + wy * vy) / v_sq
            closest_x = dx + np.clip(b, 0, 1) * vx
            closest_y = dy + np.clip(b, 0, 1) * vy
            khoang_cach_toi_tia = np.sqrt((bon_chua['x'] - closest_x)**2 + (bon_chua['y'] - closest_y)**2)
            khoang_cach_den_bon = np.sqrt(wx**2 + wy**2)
            khoang_cach_den_dau_do = np.sqrt(vx**2 + vy**2)
            bi_che_khuat = (khoang_cach_toi_tia < bon_chua['r']) & (khoang_cach_den_dau_do > khoang_cach_den_bon) & (b > 0)
        
        tong_vung_phu = tong_vung_phu | (trong_ban_kinh & ~bi_che_khuat)

    tong_vung_phu = tong_vung_phu & ~khong_gian_trong_bon
    ty_le = (np.sum(tong_vung_phu) / (xx.size - np.sum(khong_gian_trong_bon))) * 100 if xx.size > 0 else 0

    # Vẽ hình
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.contourf(xx, yy, tong_vung_phu, levels=[0.5, 1], colors=['#A8E6CF'], alpha=0.7)
    ax.plot([0, rx, rx, 0, 0], [0, 0, ry, ry, 0], 'k-', lw=2)
    
    if bon_chua:
        ax.add_patch(plt.Circle((bon_chua['x'], bon_chua['y']), bon_chua['r'], color='gray', zorder=5))
    
    for _, det in df_dets.iterrows():
        ax.plot(det['X'], det['Y'], '^', color=det['Color'].lower() if det['Color'].lower() in ['cyan', 'magenta', 'red', 'blue', 'yellow', 'green'] else 'b', markersize=10)

    ax.set_title(f"2D Gas Mapping - Coverage: {ty_le:.1f}%", fontweight='bold')
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.axis('equal')
    ax.grid(True, linestyle=':', alpha=0.5)
    
    return fig, ty_le

def generate_word_report(fig, ty_le, rx, ry):
    """Tạo báo cáo Word và chèn ảnh 2D từ bộ nhớ tạm"""
    doc = Document()
    doc.add_heading('BÁO CÁO ĐÁNH GIÁ VÙNG PHỦ HỆ THỐNG ĐO KHÍ', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('Đơn vị thực hiện: CÔNG TY TNHH CÔNG NGHỆ THIẾT BỊ DÒ KHÍ RIKEN VIET').bold = True
    doc.add_paragraph('_' * 60)
    
    doc.add_heading('1. Thông số thiết kế', level=1)
    doc.add_paragraph(f'Khu vực giám sát có kích thước: {rx}m x {ry}m. '
                      f'Hệ thống được thiết kế theo phương pháp Performance-Based nhằm tối ưu hóa điểm mù.')
    
    doc.add_heading('2. Kết quả Mô phỏng 2D', level=1)
    
    # Lưu Plot vào bộ nhớ RAM (BytesIO) thay vì ổ cứng
    img_stream = io.BytesIO()
    fig.savefig(img_stream, format='png', bbox_inches='tight', dpi=150)
    img_stream.seek(0)
    
    doc.add_picture(img_stream, width=Inches(6.0))
    doc.add_paragraph(f'Hình 1: Mô phỏng vùng phủ giao thoa. Tỷ lệ an toàn đạt: {ty_le:.1f}%').alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Lưu file Word vào bộ nhớ RAM
    doc_stream = io.BytesIO()
    doc.save(doc_stream)
    doc_stream.seek(0)
    return doc_stream

# --- (HÀM generate_scad GIỮ NGUYÊN NHƯ CŨ - Rút gọn để hiển thị) ---
def generate_scad(rx, ry, rz, df_obs, df_dets):
    scad = f"$fn=100; cube([{rx},{ry},{rz}], center=false);\n" # Code khung đơn giản
    # Trong thực tế, bạn dán lại hàm generate_scad đầy đủ ở bài trước vào đây
    return scad

# --- 4. HIỂN THỊ WEB & XUẤT FILE ---
with col_view:
    st.header("2. Kết quả Mô phỏng 2D")
    
    # Nút bấm chạy mô phỏng
    if st.button("🚀 Chạy Mô Phỏng & Cập Nhật", type="primary"):
        with st.spinner('Đang tính toán ma trận bóng mờ...'):
            fig, coverage_percent = generate_2d_plot(room_x, room_y, edited_obs, edited_dets)
            st.pyplot(fig)
            
            # Khởi tạo các file tải về
            word_stream = generate_word_report(fig, coverage_percent, room_x, room_y)
            scad_code = generate_scad(room_x, room_y, room_z, edited_obs, edited_dets)
            
            st.success("Tạo Báo cáo thành công! Tải file tại đây:")
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(label="📄 Tải Báo cáo (Word)", data=word_stream, file_name="RikenViet_GasMapping.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            with col_d2:
                st.download_button(label="🧊 Tải Mô hình (3D .scad)", data=scad_code, file_name="Model_3D.scad", mime="text/plain")
