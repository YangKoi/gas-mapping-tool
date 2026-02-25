import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import io
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import matplotlib.colors as mcolors

st.set_page_config(page_title="Riken Viet - Auto Gas Mapping", layout="wide")
st.title("🛡️ Hệ thống Tự động Thiết kế Vùng phủ Khí (>80%)")

# --- QUẢN LÝ TRẠNG THÁI (SESSION STATE) ---
if 'det_data' not in st.session_state:
    st.session_state.det_data = pd.DataFrame(columns=["ID", "X", "Y", "Z", "Radius", "Color"])

# --- 1. GIAO DIỆN NHẬP LIỆU ---
col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("1. Kích thước & Lưới không gian")
    room_x = st.number_input("Chiều dài (X) - mét", min_value=1.0, value=15.0, step=1.0)
    room_y = st.number_input("Chiều rộng (Y) - mét", min_value=1.0, value=10.0, step=1.0)
    room_z = st.number_input("Chiều cao trần (Z)", min_value=1.0, value=5.0)

    # Vẽ lưới không gian trống
    fig_grid, ax_grid = plt.subplots(figsize=(6, 4))
    ax_grid.set_xlim(0, room_x)
    ax_grid.set_ylim(0, room_y)
    ax_grid.set_xticks(np.arange(0, room_x + 1, max(1, int(room_x/10))))
    ax_grid.set_yticks(np.arange(0, room_y + 1, max(1, int(room_y/10))))
    ax_grid.grid(True, linestyle='--', color='gray', alpha=0.5)
    ax_grid.set_title("Lưới tọa độ (Tham khảo để đặt vật cản)")
    ax_grid.set_aspect('equal')
    st.pyplot(fig_grid)

with col2:
    st.header("2. Vật cản & Tự động tính Đầu dò")
    
    with st.expander("📌 Nhập Vật cản (Hình trụ)", expanded=True):
        default_obstacles = pd.DataFrame([
            {"Type": "Cylinder", "X": 7.5, "Y": 5.0, "Radius": 1.5, "Height": 3.5}
        ])
        edited_obs = st.data_editor(default_obstacles, num_rows="dynamic", use_container_width=True)

    with st.expander("⚙️ Tự động tính toán số lượng Đầu dò", expanded=True):
        model_name = st.text_input("Tên Model thiết bị", value="SD-1")
        radius_input = st.number_input("Bán kính bao phủ lý thuyết (m)", min_value=1.0, value=5.0, step=0.5)
        
        if st.button("🚀 Tự động bố trí đảm bảo >80% an toàn", type="primary"):
            spacing = radius_input * 1.5 
            nx = max(1, math.ceil(room_x / spacing))
            ny = max(1, math.ceil(room_y / spacing))
            
            x_steps = np.linspace(room_x/(2*nx), room_x - room_x/(2*nx), nx)
            y_steps = np.linspace(room_y/(2*ny), room_y - room_y/(2*ny), ny)
            
            new_dets = []
            count = 1
            # Danh sách màu sắc hợp lệ trong matplotlib
            colors = ["cyan", "magenta", "yellow", "lime", "red", "blue", "orange"]
            for x in x_steps:
                for y in y_steps:
                    new_dets.append({
                        "ID": f"{model_name} ({count:02d})",
                        "X": round(x, 1),
                        "Y": round(y, 1),
                        "Z": 2.0,
                        "Radius": radius_input,
                        "Color": colors[count % len(colors)]
                    })
                    count += 1
            
            st.session_state.det_data = pd.DataFrame(new_dets)
            st.success(f"Đã tự động rải {count-1} đầu dò!")

    st.write("📋 **Bảng Tọa độ Đầu dò (Kiểm tra và tinh chỉnh tay):**")
    edited_dets = st.data_editor(st.session_state.det_data, num_rows="dynamic", use_container_width=True)


# --- 2. CÁC HÀM XỬ LÝ LÕI (ĐÃ NÂNG CẤP HÀM VẼ 2D) ---

def check_collision(df_dets, df_obs):
    collisions = []
    if df_obs.empty or df_dets.empty: return collisions
    for _, det in df_dets.iterrows():
        for _, obs in df_obs.iterrows():
            dist = math.sqrt((det['X'] - obs['X'])**2 + (det['Y'] - obs['Y'])**2)
            if dist <= obs['Radius']:
                collisions.append(det['ID'])
    return collisions

def generate_2d_plot(rx, ry, df_obs, df_dets):
    res = 0.1
    xx, yy = np.meshgrid(np.arange(0, rx, res), np.arange(0, ry, res))
    tong_vung_phu = np.zeros_like(xx, dtype=bool)
    khong_gian_trong_bon = np.zeros_like(xx, dtype=bool)

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
    diem_kha_dung = xx.size - np.sum(khong_gian_trong_bon)
    ty_le = (np.sum(tong_vung_phu) / diem_kha_dung) * 100 if diem_kha_dung > 0 else 0

    # --- VẼ HÌNH ---
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Lớp 1: Vùng phủ tổng hợp (Màu nền xanh)
    ax.contourf(xx, yy, tong_vung_phu, levels=[0.5, 1], colors=['#A8E6CF'], alpha=0.6, zorder=1)
    
    # Lớp 2: Tường bao
    ax.plot([0, rx, rx, 0, 0], [0, 0, ry, ry, 0], 'k-', lw=2, zorder=2)
    
    # Lớp 3: Vẽ các đầu dò và vòng tròn bao phủ lý thuyết (Nét đứt)
    valid_colors = mcolors.CSS4_COLORS # Lấy danh sách màu hợp lệ của matplotlib
    for _, det in df_dets.iterrows():
        d_color = det['Color'].lower()
        # Kiểm tra nếu màu nhập vào không hợp lệ thì chuyển về màu xanh dương mặc định
        use_color = d_color if d_color in valid_colors else 'blue'
        
        # Vẽ vòng tròn nét đứt thể hiện phạm vi lý thuyết
        circle = plt.Circle((det['X'], det['Y']), det['Radius'], 
                            color=use_color, fill=False, linestyle='--', linewidth=1.5, alpha=0.8, zorder=3)
        ax.add_patch(circle)
        
        # Vẽ tâm đầu dò (Hình tam giác)
        ax.plot(det['X'], det['Y'], '^', color=use_color, markersize=12, markeredgecolor='black', zorder=5)

    # Lớp 4: Vẽ bồn chứa (Vật cản) - Đặt zorder cao hơn để che các vòng tròn nét đứt
    if bon_chua:
        tank = plt.Circle((bon_chua['x'], bon_chua['y']), bon_chua['r'], color='gray', alpha=0.9, zorder=4, label='Vật cản')
        ax.add_patch(tank)

    ax.set_title(f"Bản đồ Vùng phủ 2D (Hiển thị phạm vi lý thuyết & Thực tế)\nTỷ lệ an toàn đạt: {ty_le:.1f}%", fontweight='bold', fontsize=12)
    ax.set_xlabel("Chiều dài X (m)")
    ax.set_ylabel("Chiều rộng Y (m)")
    ax.axis('equal')
    ax.grid(True, linestyle=':', alpha=0.5, zorder=0)
    
    return fig, ty_le

def generate_word_report(fig, ty_le, rx, ry):
    doc = Document()
    doc.add_heading('BÁO CÁO ĐÁNH GIÁ VÙNG PHỦ HỆ THỐNG ĐO KHÍ', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('Đơn vị thực hiện: CÔNG TY TNHH CÔNG NGHỆ THIẾT BỊ DÒ KHÍ RIKEN VIET').bold = True
    doc.add_paragraph('_' * 60)
    
    doc.add_heading('1. Thông số thiết kế', level=1)
    doc.add_paragraph(f'Khu vực giám sát có kích thước: {rx}m x {ry}m. Hệ thống được thiết kế theo phương pháp mô phỏng tối ưu hóa điểm mù.')
    
    doc.add_heading('2. Kết quả Mô phỏng 2D', level=1)
    doc.add_paragraph('Hình ảnh dưới đây thể hiện các vòng tròn bao phủ lý thuyết (nét đứt) và vùng phủ thực tế sau khi tính toán hiệu ứng bóng mờ do vật cản (vùng màu xanh).')
    img_stream = io.BytesIO()
    fig.savefig(img_stream, format='png', bbox_inches='tight', dpi=150)
    img_stream.seek(0)
    
    doc.add_picture(img_stream, width=Inches(6.0))
    doc.add_paragraph(f'Hình 1: Bản đồ nhiệt mô phỏng. Tỷ lệ an toàn đạt: {ty_le:.1f}%').alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc_stream = io.BytesIO()
    doc.save(doc_stream)
    doc_stream.seek(0)
    return doc_stream

def generate_scad(rx, ry, rz, df_obs, df_dets):
    scad = f"$fn=100;\nmodule room_frame() {{\n color(\"Black\") {{\n"
    scad += f"  translate([0,0,0]) cylinder(r=0.05, h={rz}); translate([{rx},0,0]) cylinder(r=0.05, h={rz});\n"
    scad += f"  translate([0,{ry},0]) cylinder(r=0.05, h={rz}); translate([{rx},{ry},0]) cylinder(r=0.05, h={rz});\n"
    scad += f"  hull() {{ translate([0,0,0]) sphere(r=0.05); translate([{rx},0,0]) sphere(r=0.05); }}\n"
    scad += f"  hull() {{ translate([0,0,0]) sphere(r=0.05); translate([0,{ry},0]) sphere(r=0.05); }}\n"
    scad += f"  hull() {{ translate([{rx},{ry},0]) sphere(r=0.05); translate([{rx},0,0]) sphere(r=0.05); }}\n"
    scad += f"  hull() {{ translate([{rx},{ry},0]) sphere(r=0.05); translate([0,{ry},0]) sphere(r=0.05); }}\n"
    scad += f" }}\n}}\nmodule obstacles() {{\n"
    for _, row in df_obs.iterrows():
        scad += f'    color("DimGray", 1.0) translate([{row["X"]}, {row["Y"]}, 0]) cylinder(r={row["Radius"]}, h={row["Height"]});\n'
    scad += "}\nroom_frame();\nintersection() {\n"
    scad += f"    cube([{rx}, {ry}, {rz}]);\n    union() {{\n        obstacles();\n\n"
    valid_colors = mcolors.CSS4_COLORS
    for _, row in df_dets.iterrows():
        d_color = row["Color"].lower()
        use_color = d_color if d_color in valid_colors else 'red'
        scad += f'        // {row["ID"]}\n'
        scad += f'        color("{use_color}") translate([{row["X"]}, {row["Y"]}, {row["Z"]}]) sphere(r=0.2);\n'
        scad += f'        color("{use_color}", 0.3) difference() {{\n'
        scad += f'            translate([{row["X"]}, {row["Y"]}, {row["Z"]}]) sphere(r={row["Radius"]});\n'
        scad += f'            obstacles();\n        }}\n'
    scad += "    }\n}\n"
    return scad


# --- 3. KIỂM TRA & XUẤT KẾT QUẢ TỔNG HỢP ---
st.markdown("---")
if st.button("📊 Xuất Báo cáo & Lập Bản đồ Bóng mờ (Shadowing)", use_container_width=True, type='primary'):
    if edited_dets.empty:
        st.warning("⚠️ Vui lòng bấm 'Tự động bố trí' hoặc nhập tay ít nhất 1 đầu dò vào bảng!")
    else:
        collided_dets = check_collision(edited_dets, edited_obs)
        
        if collided_dets:
            st.error(f"⛔ CẢNH BÁO VA CHẠM: Đầu dò **{', '.join(collided_dets)}** đang bị đặt trùng vị trí với vật cản! Vui lòng chỉnh lại tọa độ trên bảng.")
        else:
            with st.spinner('Đang tính toán và kết xuất tài liệu...'):
                # Render Plot 2D
                fig, coverage_percent = generate_2d_plot(room_x, room_y, edited_obs, edited_dets)
                st.pyplot(fig)
                
                # Render Files
                word_stream = generate_word_report(fig, coverage_percent, room_x, room_y)
                scad_code = generate_scad(room_x, room_y, room_z, edited_obs, edited_dets)
                
                if coverage_percent >= 80:
                    st.success(f"✅ TUYỆT VỜI! Tỷ lệ bao phủ đạt chuẩn an toàn: {coverage_percent:.1f}% (Mục tiêu >80%)")
                else:
                    st.warning(f"⚠️ Cảnh báo: Tỷ lệ bao phủ chỉ đạt {coverage_percent:.1f}%. Cần bổ sung đầu dò hoặc điều chỉnh vị trí để đạt mục tiêu >80%.")
                
                # Nút tải file
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        label="📄 Tải Báo cáo Kỹ thuật (Word .docx)", 
                        data=word_stream, 
                        file_name="Bao_Cao_GasMapping_RikenViet.docx", 
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary"
                    )
                with col_d2:
                    st.download_button(
                        label="🧊 Tải Mô hình Không gian (3D .scad)", 
                        data=scad_code, 
                        file_name="Mo_Hinh_3D.scad", 
                        mime="text/plain"
                    )
