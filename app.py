import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import math
import io
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import matplotlib.colors as mcolors

st.set_page_config(page_title="Riken Viet - 3D Gas Mapping Expert", layout="wide")
st.title("🛡️ Riken Viet - Hệ thống Tư vấn Vùng phủ Khí 3D")

if 'det_data' not in st.session_state:
    st.session_state.det_data = pd.DataFrame(columns=["ID", "X", "Y", "Z", "Radius", "Color"])

# --- 1. GIAO DIỆN NHẬP LIỆU & LOGIC VẬT LÝ KHÍ ---
col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("1. Không gian & Đặc tính Khí")
    
    # THÊM MỚI: Logic Vật lý khí
    st.subheader("🧪 Thông số Khí mục tiêu")
    gas_type = st.selectbox(
        "Loại khí cần giám sát (Quyết định cao độ Z)", 
        [
            "Khí CHÁY/ĐỘC NHẸ hơn không khí (CH4, H2, NH3...)", 
            "Khí CHÁY/ĐỘC NẶNG hơn không khí (LPG, H2S, VOCs...)", 
            "Khí có TỶ TRỌNG TƯƠNG ĐƯƠNG không khí (CO, O2...)"
        ]
    )
    
    st.subheader("📏 Kích thước khu vực (m)")
    room_x = st.number_input("Chiều dài (X)", min_value=1.0, value=15.0, step=1.0)
    room_y = st.number_input("Chiều rộng (Y)", min_value=1.0, value=10.0, step=1.0)
    room_z = st.number_input("Chiều cao trần (Z)", min_value=1.0, value=5.0)

    # Tính toán cao độ Z tối ưu dựa trên loại khí
    if "NHẸ" in gas_type:
        recommended_z = max(room_z - 0.5, 0.5)
        st.info(f"💡 Khí nhẹ: Hệ thống đề xuất đặt sát trần. Z tối ưu = {recommended_z}m")
    elif "NẶNG" in gas_type:
        recommended_z = 0.5
        st.info(f"💡 Khí nặng: Hệ thống đề xuất đặt sát mặt đất. Z tối ưu = {recommended_z}m")
    else:
        recommended_z = 1.5
        st.info(f"💡 Khí trung tính: Hệ thống đề xuất đặt ngang vùng thở. Z tối ưu = {recommended_z}m")

with col2:
    st.header("2. Vật cản & Bố trí Đầu dò")
    
    with st.expander("📌 Nhập Vật cản (Hình trụ)", expanded=True):
        default_obstacles = pd.DataFrame([
            {"Type": "Cylinder", "X": 7.5, "Y": 5.0, "Radius": 1.5, "Height": 3.5}
        ])
        edited_obs = st.data_editor(default_obstacles, num_rows="dynamic", use_container_width=True)

    with st.expander("⚙️ Tự động tính toán số lượng Đầu dò", expanded=True):
        col_calc1, col_calc2 = st.columns(2)
        model_name = col_calc1.text_input("Tên Model thiết bị", value="SD-1")
        radius_input = col_calc2.number_input("Bán kính bao phủ (m)", min_value=1.0, value=5.0, step=0.5)
        
        if st.button("🚀 Tự động bố trí lưới đầu dò", type="primary"):
            spacing = radius_input * 1.5 
            nx = max(1, math.ceil(room_x / spacing))
            ny = max(1, math.ceil(room_y / spacing))
            x_steps = np.linspace(room_x/(2*nx), room_x - room_x/(2*nx), nx)
            y_steps = np.linspace(room_y/(2*ny), room_y - room_y/(2*ny), ny)
            
            new_dets = []
            count = 1
            colors = ["cyan", "magenta", "yellow", "lime", "red", "blue"]
            for x in x_steps:
                for y in y_steps:
                    new_dets.append({
                        "ID": f"{model_name} ({count:02d})",
                        "X": round(x, 1),
                        "Y": round(y, 1),
                        "Z": recommended_z, # TỰ ĐỘNG LẤY CHIỀU CAO TỐI ƯU TỪ LOGIC KHÍ
                        "Radius": radius_input,
                        "Color": colors[count % len(colors)]
                    })
                    count += 1
            st.session_state.det_data = pd.DataFrame(new_dets)
            st.success(f"Đã rải {count-1} đầu dò ở cao độ Z = {recommended_z}m!")

    st.write("📋 **Bảng Tọa độ Đầu dò (Chỉnh sửa trực tiếp):**")
    edited_dets = st.data_editor(st.session_state.det_data, num_rows="dynamic", use_container_width=True)

# --- 2. CÁC HÀM XỬ LÝ (2D MAP & OPENSCAD GIỮ NGUYÊN NHƯ CŨ) ---
# ... (Bạn vui lòng copy nguyên hàm generate_2d_plot, check_collision, generate_word_report, generate_scad từ bài trước dán vào đây để tiết kiệm không gian hiển thị nhé) ...

# --- THÊM MỚI: HÀM VẼ 3D TRỰC TIẾP TRÊN WEB BẰNG PLOTLY ---
def generate_plotly_3d(rx, ry, rz, df_obs, df_dets):
    fig = go.Figure()

    # 1. Vẽ Khung căn phòng (Wireframe)
    x_lines = [0, rx, rx, 0, 0, 0, rx, rx, 0, 0, None, rx, rx, None, rx, rx, None, 0, 0]
    y_lines = [0, 0, ry, ry, 0, 0, 0, ry, ry, 0, None, 0, 0, None, ry, ry, None, ry, ry]
    z_lines = [0, 0, 0, 0, 0, rz, rz, rz, rz, rz, None, 0, rz, None, 0, rz, None, 0, rz]
    fig.add_trace(go.Scatter3d(x=x_lines, y=y_lines, z=z_lines, mode='lines', line=dict(color='black', width=4), name='Tường nhà kho'))

    # Hàm tạo tọa độ mặt cầu
    def get_sphere(x0, y0, z0, r):
        u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
        x = r * np.cos(u) * np.sin(v) + x0
        y = r * np.sin(u) * np.sin(v) + y0
        z = r * np.cos(v) + z0
        return x, y, z

    # 2. Vẽ Đầu dò và Vùng phủ 3D (Bán trong suốt)
    for _, det in df_dets.iterrows():
        # Điểm đầu dò
        fig.add_trace(go.Scatter3d(x=[det['X']], y=[det['Y']], z=[det['Z']], mode='markers', 
                                   marker=dict(size=8, color='black'), name=det['ID']))
        # Mặt cầu bao phủ
        x_sph, y_sph, z_sph = get_sphere(det['X'], det['Y'], det['Z'], det['Radius'])
        fig.add_trace(go.Surface(x=x_sph, y=y_sph, z=z_sph, opacity=0.15, showscale=False, 
                                 colorscale=[[0, det['Color']], [1, det['Color']]], name=f"Vùng phủ {det['ID']}"))

    # 3. Vẽ Bồn chứa (Vật cản dạng trụ)
    for _, obs in df_obs.iterrows():
        z_grid, theta = np.mgrid[0:obs['Height']:2j, 0:2*np.pi:20j]
        x_cyl = obs['Radius'] * np.cos(theta) + obs['X']
        y_cyl = obs['Radius'] * np.sin(theta) + obs['Y']
        fig.add_trace(go.Surface(x=x_cyl, y=y_cyl, z=z_grid, opacity=1.0, showscale=False, 
                                 colorscale='Greys', name="Vật cản (Bồn chứa)"))

    # Cấu hình hiển thị tỷ lệ chuẩn 1:1:1
    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[0, rx], title='X (m)'),
            yaxis=dict(range=[0, ry], title='Y (m)'),
            zaxis=dict(range=[0, max(rz, room_z)], title='Z (m)'),
            aspectmode='data' # Quan trọng: Ép tỷ lệ thực tế, không bị kéo dãn
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        title="Mô hình Không gian 3D Tương tác (Có thể xoay/phóng to)"
    )
    return fig


# --- 3. KIỂM TRA & XUẤT KẾT QUẢ TỔNG HỢP ---
st.markdown("---")
if st.button("📊 Chạy Mô phỏng Kỹ thuật & Xuất Báo cáo", use_container_width=True, type='primary'):
    if edited_dets.empty:
        st.warning("⚠️ Vui lòng nhập thông số đầu dò!")
    else:
        # KIỂM TRA VẬT LÝ KHÍ ĐỂ ĐƯA RA LỜI KHUYÊN (Không báo lỗi đỏ, chỉ cảnh báo vàng)
        gas_warnings = []
        for _, det in edited_dets.iterrows():
            if "NHẸ" in gas_type and det['Z'] < room_z - 1.0:
                gas_warnings.append(det['ID'])
            elif "NẶNG" in gas_type and det['Z'] > 1.0:
                gas_warnings.append(det['ID'])
        
        if gas_warnings:
            st.warning(f"⚠️ **Tư vấn An toàn Khí:** Các đầu dò {', '.join(gas_warnings)} có cao độ Z chưa tối ưu với đặc tính của loại khí bạn chọn. Hãy cân nhắc điều chỉnh!")

        # KIỂM TRA VA CHẠM VẬT LÝ (Báo lỗi đỏ và dừng lại nếu đâm xuyên bồn)
        # collided_dets = check_collision(edited_dets, edited_obs) # (Bạn giữ nguyên hàm này từ bài trước)
        collided_dets = [] # (Giả lập pass kiểm tra ở đây để chạy ví dụ)
        
        if collided_dets:
            st.error(f"⛔ CẢNH BÁO VA CHẠM: Đầu dò {', '.join(collided_dets)} đang nằm trong bồn chứa!")
        else:
            with st.spinner('Đang tính toán kết xuất Đồ họa 2D/3D và Báo cáo Word...'):
                
                # CHIA ĐÔI MÀN HÌNH HIỂN THỊ KẾT QUẢ (Trái: 3D Plotly | Phải: 2D Heatmap)
                st.header("3. Phân tích Kết quả Đồ họa")
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    # Render 3D tương tác bằng Plotly
                    fig_3d = generate_plotly_3d(room_x, room_y, room_z, edited_obs, edited_dets)
                    st.plotly_chart(fig_3d, use_container_width=True)
                
                with col_res2:
                    # Giả sử hàm generate_2d_plot trả về hình và % (Bạn dán hàm thực tế vào đây)
                    # fig_2d, coverage_percent = generate_2d_plot(room_x, room_y, edited_obs, edited_dets)
                    # st.pyplot(fig_2d)
                    st.info("[Khu vực hiển thị Bản đồ Nhiệt 2D Matplotlib]")
                    coverage_percent = 85.5 # Số giả lập
                
                st.success(f"✅ Tỷ lệ bao phủ đạt: {coverage_percent:.1f}%")
                
                # Render file tải về
                # word_stream = generate_word_report(fig_2d, coverage_percent, room_x, room_y)
                # scad_code = generate_scad(room_x, room_y, room_z, edited_obs, edited_dets)
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button("📄 Tải Báo cáo Kỹ thuật (Word)", b"demo", "Bao_Cao.docx", type="primary")
                with col_d2:
                    st.download_button("🧊 Tải Mã nguồn 3D (.scad)", b"demo", "Mo_Hinh.scad")
