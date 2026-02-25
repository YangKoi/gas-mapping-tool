import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import io
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

st.set_page_config(page_title="Riken Viet - Auto Gas Mapping", layout="wide")
st.title("🛡️ Hệ thống Tự động Thiết kế Vùng phủ Khí (>80%)")

# --- QUẢN LÝ TRẠNG THÁI (SESSION STATE) ---
# Cần dùng session_state để lưu bảng đầu dò, giúp thuật toán có thể ghi đè dữ liệu mới vào
if 'det_data' not in st.session_state:
    st.session_state.det_data = pd.DataFrame(columns=["ID", "X", "Y", "Z", "Radius", "Color"])

# --- GIAO DIỆN NHẬP LIỆU ---
col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("1. Kích thước & Lưới không gian")
    room_x = st.number_input("Chiều dài (X) - mét", min_value=1.0, value=15.0, step=1.0)
    room_y = st.number_input("Chiều rộng (Y) - mét", min_value=1.0, value=10.0, step=1.0)
    room_z = st.number_input("Chiều cao trần (Z)", min_value=1.0, value=5.0)

    # VẼ LƯỚI TỌA ĐỘ TRỐNG NGAY LẬP TỨC ĐỂ NGƯỜI DÙNG DÒ TỌA ĐỘ
    fig_grid, ax_grid = plt.subplots(figsize=(6, 4))
    ax_grid.set_xlim(0, room_x)
    ax_grid.set_ylim(0, room_y)
    ax_grid.set_xticks(np.arange(0, room_x + 1, max(1, int(room_x/10))))
    ax_grid.set_yticks(np.arange(0, room_y + 1, max(1, int(room_y/10))))
    ax_grid.grid(True, linestyle='--', color='gray', alpha=0.7)
    ax_grid.set_title("Lưới tọa độ (Dùng để xác định vị trí Vật cản)")
    st.pyplot(fig_grid)

with col2:
    st.header("2. Vật cản & Tự động tính Đầu dò")
    
    with st.expander("📌 Nhập Vật cản (Dựa vào lưới tọa độ bên trái)", expanded=True):
        default_obstacles = pd.DataFrame([
            {"Type": "Cylinder", "X": 7.5, "Y": 5.0, "Radius": 1.5, "Height": 3.5}
        ])
        edited_obs = st.data_editor(default_obstacles, num_rows="dynamic", use_container_width=True)

    with st.expander("⚙️ Tự động tính toán số lượng Đầu dò", expanded=True):
        model_name = st.text_input("Tên Model thiết bị", value="SD-1")
        radius_input = st.number_input("Bán kính bao phủ lý thuyết (m)", min_value=1.0, value=5.0, step=0.5)
        
        if st.button("🚀 Tự động bố trí đảm bảo >80% an toàn", type="primary"):
            # THUẬT TOÁN TỰ ĐỘNG RẢI ĐẦU DÒ (Grid Placement)
            # Để đảm bảo phủ >80%, khoảng cách giữa các tâm đầu dò tối ưu là 1.5 * Radius
            spacing = radius_input * 1.5 
            nx = max(1, math.ceil(room_x / spacing))
            ny = max(1, math.ceil(room_y / spacing))
            
            x_steps = np.linspace(room_x/(2*nx), room_x - room_x/(2*nx), nx)
            y_steps = np.linspace(room_y/(2*ny), room_y - room_y/(2*ny), ny)
            
            new_dets = []
            count = 1
            colors = ["Cyan", "Magenta", "Yellow", "Green"]
            for x in x_steps:
                for y in y_steps:
                    new_dets.append({
                        "ID": f"{model_name} ({count:02d})",
                        "X": round(x, 1),
                        "Y": round(y, 1),
                        "Z": 2.0, # Độ cao mặc định
                        "Radius": radius_input,
                        "Color": colors[count % 4]
                    })
                    count += 1
            
            # Cập nhật vào Session State để hiển thị ra bảng
            st.session_state.det_data = pd.DataFrame(new_dets)
            st.success(f"Đã tự động rải {count-1} đầu dò!")

    st.write("📋 **Bảng Tọa độ Đầu dò (Có thể chỉnh sửa tay sau khi tự động rải):**")
    edited_dets = st.data_editor(st.session_state.det_data, num_rows="dynamic", use_container_width=True)

# --- PHẦN 3 & 4 (Hàm vẽ 2D, xuất SCAD, xuất Word giữ nguyên như bản trước) ---
# ... (Bạn copy nguyên các hàm generate_2d_plot, generate_word_report, generate_scad từ bài trước dán vào đây) ...

# NÚT HIỂN THỊ KẾT QUẢ TỔNG HỢP Ở DƯỚI CÙNG
st.markdown("---")
if st.button("📊 Xuất Báo cáo & Lập Bản đồ Bóng mờ (Shadowing)", use_container_width=True):
    if edited_dets.empty:
        st.warning("Vui lòng bấm 'Tự động bố trí' hoặc nhập tay ít nhất 1 đầu dò!")
    else:
        # Giả định bạn đã dán các hàm vào, đoạn này gọi hàm như cũ
        # fig, coverage_percent = generate_2d_plot(room_x, room_y, edited_obs, edited_dets)
        # st.pyplot(fig)
        st.info("Khu vực này sẽ hiển thị Plot 2D và các nút Tải Word, Tải file 3D SCAD như bản trước.")
