import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import matplotlib.colors as mcolors
import math
import io
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

st.set_page_config(page_title="Riken Viet - 3D Gas Mapping Expert", layout="wide")
st.title("🛡️ Riken Viet - Hệ thống Tư vấn Vùng phủ Khí 3D")

if 'det_data' not in st.session_state:
    st.session_state.det_data = pd.DataFrame(columns=["ID", "X", "Y", "Z", "Radius", "Color"])

# ==========================================
# 1. GIAO DIỆN NHẬP LIỆU & LƯỚI TỌA ĐỘ
# ==========================================
col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("1. Không gian & Đặc tính Khí")
    
    st.subheader("🧪 Thông số Khí mục tiêu")
    gas_type = st.selectbox(
        "Loại khí cần giám sát:", 
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

    if "NHẸ" in gas_type: recommended_z = max(room_z - 0.5, 0.5)
    elif "NẶNG" in gas_type: recommended_z = 0.5
    else: recommended_z = 1.5
    st.info(f"💡 Cao độ Z tối ưu đề xuất: {recommended_z}m")

    # PHỤC HỒI: VẼ LƯỚI TỌA ĐỘ ĐỂ NHẬP LIỆU
    fig_grid, ax_grid = plt.subplots(figsize=(6, 4))
    ax_grid.set_xlim(0, room_x)
    ax_grid.set_ylim(0, room_y)
    ax_grid.set_xticks(np.arange(0, room_x + 1, max(1, int(room_x/10))))
    ax_grid.set_yticks(np.arange(0, room_y + 1, max(1, int(room_y/10))))
    ax_grid.grid(True, linestyle='--', color='gray', alpha=0.5)
    ax_grid.set_title("Lưới tọa độ mặt bằng (Nhìn từ trên xuống)")
    ax_grid.set_aspect('equal')
    st.pyplot(fig_grid)

with col2:
    st.header("2. Vật cản & Bố trí Đầu dò")
    
    with st.expander("📌 Nhập Vật cản (Hình trụ)", expanded=True):
        default_obstacles = pd.DataFrame([{"Type": "Cylinder", "X": 7.5, "Y": 5.0, "Radius": 1.5, "Height": 3.5}])
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
            
            new_dets, count = [], 1
            colors = ["cyan", "magenta", "yellow", "lime", "red", "blue"]
            for x in x_steps:
                for y in y_steps:
                    new_dets.append({
                        "ID": f"{model_name} ({count:02d})", "X": round(x, 1), "Y": round(y, 1),
                        "Z": recommended_z, "Radius": radius_input, "Color": colors[count % len(colors)]
                    })
                    count += 1
            st.session_state.det_data = pd.DataFrame(new_dets)
            st.success(f"Đã rải {count-1} đầu dò!")

    st.write("📋 **Bảng Tọa độ Đầu dò:**")
    edited_dets = st.data_editor(st.session_state.det_data, num_rows="dynamic", use_container_width=True)


# ==========================================
# 2. CÁC HÀM XỬ LÝ LÕI
# ==========================================
def check_collision(df_dets, df_obs):
    collisions = []
    if df_obs.empty or df_dets.empty: return collisions
    for _, det in df_dets.iterrows():
        for _, obs in df_obs.iterrows():
            if math.sqrt((det['X'] - obs['X'])**2 + (det['Y'] - obs['Y'])**2) <= obs['Radius']:
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
            v_sq = vx**2 + vy**2; v_sq[v_sq == 0] = 1e-10
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

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.contourf(xx, yy, tong_vung_phu, levels=[0.5, 1], colors=['#A8E6CF'], alpha=0.6, zorder=1)
    ax.plot([0, rx, rx, 0, 0], [0, 0, ry, ry, 0], 'k-', lw=2, zorder=2)
    
    valid_colors = mcolors.CSS4_COLORS
    for _, det in df_dets.iterrows():
        d_color = det['Color'].lower()
        use_color = d_color if d_color in valid_colors else 'blue'
        ax.add_patch(plt.Circle((det['X'], det['Y']), det['Radius'], color=use_color, fill=False, linestyle='--', lw=1.5, zorder=3))
        ax.plot(det['X'], det['Y'], '^', color=use_color, markersize=10, markeredgecolor='black', zorder=5)

    if bon_chua:
        ax.add_patch(plt.Circle((bon_chua['x'], bon_chua['y']), bon_chua['r'], color='gray', alpha=0.9, zorder=4))

    ax.set_title(f"Bản đồ Vùng phủ 2D - An toàn: {ty_le:.1f}%", fontweight='bold')
    ax.axis('equal'); ax.grid(True, linestyle=':', alpha=0.5, zorder=0)
    return fig, ty_le

def generate_plotly_3d(rx, ry, rz, df_obs, df_dets):
    fig = go.Figure()
    # Khung phòng
    x_lines = [0, rx, rx, 0, 0, 0, rx, rx, 0, 0, None, rx, rx, None, rx, rx, None, 0, 0]
    y_lines = [0, 0, ry, ry, 0, 0, 0, ry, ry, 0, None, 0, 0, None, ry, ry, None, ry, ry]
    z_lines = [0, 0, 0, 0, 0, rz, rz, rz, rz, rz, None, 0, rz, None, 0, rz, None, 0, rz]
    fig.add_trace(go.Scatter3d(x=x_lines, y=y_lines, z=z_lines, mode='lines', line=dict(color='black', width=3), name='Tường'))

    def get_sphere(x0, y0, z0, r):
        u, v = np.mgrid[0:2*np.pi:20j, 0:np.pi:10j]
        return r * np.cos(u) * np.sin(v) + x0, r * np.sin(u) * np.sin(v) + y0, r * np.cos(v) + z0

    for _, det in df_dets.iterrows():
        fig.add_trace(go.Scatter3d(x=[det['X']], y=[det['Y']], z=[det['Z']], mode='markers', marker=dict(size=6, color='black'), name=det['ID']))
        x_sph, y_sph, z_sph = get_sphere(det['X'], det['Y'], det['Z'], det['Radius'])
        fig.add_trace(go.Surface(x=x_sph, y=y_sph, z=z_sph, opacity=0.15, showscale=False, colorscale=[[0, det['Color']], [1, det['Color']]]))

    for _, obs in df_obs.iterrows():
        z_grid, theta = np.mgrid[0:obs['Height']:2j, 0:2*np.pi:20j]
        fig.add_trace(go.Surface(x=obs['Radius'] * np.cos(theta) + obs['X'], y=obs['Radius'] * np.sin(theta) + obs['Y'], z=z_grid, opacity=1.0, showscale=False, colorscale='Greys'))

    fig.update_layout(scene=dict(xaxis=dict(range=[0, rx]), yaxis=dict(range=[0, ry]), zaxis=dict(range=[0, max(rz, 5)]), aspectmode='data'), margin=dict(l=0, r=0, b=0, t=30))
    return fig

# CẬP NHẬT: THÊM ẢNH 3D VÀO WORD
def generate_word_report(fig_2d, img_3d_bytes, ty_le, rx, ry):
    doc = Document()
    doc.add_heading('BÁO CÁO ĐÁNH GIÁ VÙNG PHỦ HỆ THỐNG ĐO KHÍ', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('Đơn vị thực hiện: CÔNG TY TNHH CÔNG NGHỆ THIẾT BỊ DÒ KHÍ RIKEN VIET').bold = True
    doc.add_paragraph('_' * 60)
    
    doc.add_heading('1. Thông số thiết kế', level=1)
    doc.add_paragraph(f'Khu vực giám sát có kích thước: {rx}m x {ry}m. Tỷ lệ an toàn đạt: {ty_le:.1f}%.')
    
    # Chèn ảnh 2D
    doc.add_heading('2. Kết quả Mô phỏng 2D (Mặt bằng)', level=1)
    img_2d_stream = io.BytesIO()
    fig_2d.savefig(img_2d_stream, format='png', bbox_inches='tight', dpi=150)
    img_2d_stream.seek(0)
    doc.add_picture(img_2d_stream, width=Inches(6.0))
    doc.add_paragraph('Hình 1: Bản đồ vùng phủ giao thoa và hiệu ứng bóng mờ.').alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Chèn ảnh 3D
    doc.add_heading('3. Phân bổ Không gian 3D', level=1)
    if img_3d_bytes:
        doc.add_picture(img_3d_bytes, width=Inches(6.0))
        doc.add_paragraph('Hình 2: Trực quan hóa cao độ Z của hệ thống đầu dò.').alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc_stream = io.BytesIO()
    doc.save(doc_stream)
    doc_stream.seek(0)
    return doc_stream

def generate_scad(rx, ry, rz, df_obs, df_dets):
    scad = f"$fn=100;\nmodule room_frame() {{\n color(\"Black\") {{\n  translate([0,0,0]) cylinder(r=0.05, h={rz}); translate([{rx},0,0]) cylinder(r=0.05, h={rz});\n  translate([0,{ry},0]) cylinder(r=0.05, h={rz}); translate([{rx},{ry},0]) cylinder(r=0.05, h={rz});\n  hull() {{ translate([0,0,0]) sphere(r=0.05); translate([{rx},0,0]) sphere(r=0.05); }}\n  hull() {{ translate([0,0,0]) sphere(r=0.05); translate([0,{ry},0]) sphere(r=0.05); }}\n  hull() {{ translate([{rx},{ry},0]) sphere(r=0.05); translate([{rx},0,0]) sphere(r=0.05); }}\n  hull() {{ translate([{rx},{ry},0]) sphere(r=0.05); translate([0,{ry},0]) sphere(r=0.05); }}\n }}\n}}\nmodule obstacles() {{\n"
    for _, row in df_obs.iterrows(): scad += f'    color("DimGray", 1.0) translate([{row["X"]}, {row["Y"]}, 0]) cylinder(r={row["Radius"]}, h={row["Height"]});\n'
    scad += "}\nroom_frame();\nintersection() {\n" + f"    cube([{rx}, {ry}, {rz}]);\n    union() {{\n        obstacles();\n\n"
    valid_colors = mcolors.CSS4_COLORS
    for _, row in df_dets.iterrows():
        c = row["Color"].lower(); use_c = c if c in valid_colors else 'red'
        scad += f'        color("{use_c}") translate([{row["X"]}, {row["Y"]}, {row["Z"]}]) sphere(r=0.2);\n        color("{use_c}", 0.3) difference() {{\n            translate([{row["X"]}, {row["Y"]}, {row["Z"]}]) sphere(r={row["Radius"]});\n            obstacles();\n        }}\n'
    scad += "    }\n}\n"
    return scad


# ==========================================
# 3. KẾT XUẤT ĐỒ HỌA & BÁO CÁO
# ==========================================
st.markdown("---")
if st.button("📊 Chạy Mô phỏng & Xuất Báo cáo Tự động", use_container_width=True, type='primary'):
    if edited_dets.empty:
        st.warning("⚠️ Vui lòng nhập thông số đầu dò!")
    else:
        # Cảnh báo cao độ khí
        warnings = [d['ID'] for _, d in edited_dets.iterrows() if ("NHẸ" in gas_type and d['Z'] < room_z - 1.0) or ("NẶNG" in gas_type and d['Z'] > 1.0)]
        if warnings: st.warning(f"⚠️ Tư vấn: Các đầu dò {', '.join(warnings)} có cao độ Z chưa tối ưu với đặc tính khí!")

        # Cảnh báo va chạm
        collided = check_collision(edited_dets, edited_obs)
        if collided:
            st.error(f"⛔ LỖI: Đầu dò {', '.join(collided)} đang đâm xuyên vào vật cản!")
        else:
            with st.spinner('Đang kết xuất bản vẽ và tạo File Word...'):
                st.header("3. Kết quả Mô phỏng")
                col_res1, col_res2 = st.columns(2)
                
                # Vẽ 3D Plotly
                fig_3d = generate_plotly_3d(room_x, room_y, room_z, edited_obs, edited_dets)
                with col_res1: st.plotly_chart(fig_3d, use_container_width=True)

                # Vẽ 2D Matplotlib
                fig_2d, coverage = generate_2d_plot(room_x, room_y, edited_obs, edited_dets)
                with col_res2: st.pyplot(fig_2d)

                # Chụp ảnh 3D Plotly lưu vào RAM (Cần thư viện kaleido)
                img_3d_bytes = io.BytesIO()
                try:
                    fig_3d.write_image(img_3d_bytes, format='png', width=800, height=600)
                    img_3d_bytes.seek(0)
                except Exception as e:
                    img_3d_bytes = None # Nếu lỗi kaleido, bỏ qua ảnh 3D trong Word
                    st.error("Chưa cài đặt thư viện 'kaleido' nên ảnh 3D sẽ không hiện trong Word.")

                # Render File
                word_stream = generate_word_report(fig_2d, img_3d_bytes, coverage, room_x, room_y)
                scad_code = generate_scad(room_x, room_y, room_z, edited_obs, edited_dets)
                
                st.success(f"✅ Tỷ lệ bao phủ: {coverage:.1f}%")
                col_d1, col_d2 = st.columns(2)
                with col_d1: st.download_button("📄 Tải Báo cáo (Word)", word_stream, "Bao_Cao.docx", type="primary")
                with col_d2: st.download_button("🧊 Tải Mã nguồn (.scad)", scad_code, "Mo_Hinh.scad")
