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
from shapely.geometry import Point, LineString, Polygon
import shapely.affinity as affinity
from matplotlib.path import Path

# ==========================================
# CẤU HÌNH TRANG WEB
# ==========================================
st.set_page_config(page_title="Riken Viet - Enterprise Gas Mapping", layout="wide")
st.title("🛡️ Riken Viet - Hệ thống Thiết kế Vùng phủ Khí Đa lớp (3D) - Ver.0")

if 'room_data' not in st.session_state:
    st.session_state.room_data = pd.DataFrame({"X": [0, 15, 15, 0], "Y": [0, 0, 10, 10]}) 
if 'obs_data' not in st.session_state:
    st.session_state.obs_data = pd.DataFrame([
        {"Type": "Cylinder", "X": 7.5, "Y": 5.0, "Width_Radius": 1.5, "Length": 0.0, "Height": 4.0, "Angle": 0}
    ])
if 'det_data' not in st.session_state:
    st.session_state.det_data = pd.DataFrame(columns=["ID", "Gas", "X", "Y", "Z", "Radius", "Color"])

# ==========================================
# 1. GIAO DIỆN NHẬP LIỆU & LƯỚI TỌA ĐỘ
# ==========================================
col_input1, col_input2 = st.columns([1, 1.4])

with col_input1:
    st.header("1. Kiến trúc Phòng Không gian")
    
    room_z = st.number_input("Chiều cao trần (Z) - mét", min_value=1.0, value=5.0)

    st.subheader("📐 Tọa độ Đỉnh tường (Mặt bằng)")
    col_r1, col_r2 = st.columns(2)
    with col_r1: quick_x = st.number_input("Tạo nhanh Chiều Dài (X)", value=15.0)
    with col_r2: quick_y = st.number_input("Tạo nhanh Chiều Rộng (Y)", value=10.0)
    
    if st.button("🔄 Cập nhật thành Phòng Chữ Nhật", use_container_width=True):
        st.session_state.room_data = pd.DataFrame({"X": [0, quick_x, quick_x, 0], "Y": [0, 0, quick_y, quick_y]})
        st.rerun()
    
    st.caption("Hoặc tự do sửa tọa độ dưới đây để tạo phòng đa giác (L, U...):")
    edited_room = st.data_editor(st.session_state.room_data, num_rows="dynamic", use_container_width=True)
    
    # VẼ LƯỚI KHÔNG GIAN
    if len(edited_room) >= 3:
        room_coords = list(zip(edited_room['X'], edited_room['Y']))
        room_poly = Polygon(room_coords)
        
        fig_grid, ax_grid = plt.subplots(figsize=(6, 5))
        x_ext, y_ext = room_poly.exterior.xy
        ax_grid.plot(x_ext, y_ext, color='#333333', linewidth=2)
        ax_grid.fill(x_ext, y_ext, alpha=0.1, color='blue')
        
        # Vẽ vật cản lên lưới
        for _, obs in st.session_state.obs_data.iterrows():
            if obs['Type'] == 'Cylinder':
                c = plt.Circle((obs['X'], obs['Y']), obs['Width_Radius'], color='gray', alpha=0.5)
                ax_grid.add_patch(c)
            elif obs['Type'] == 'Box':
                w, l = obs['Width_Radius'], obs['Length']
                box = Polygon([(obs['X']-w/2, obs['Y']-l/2), (obs['X']+w/2, obs['Y']-l/2),
                               (obs['X']+w/2, obs['Y']+l/2), (obs['X']-w/2, obs['Y']+l/2)])
                box = affinity.rotate(box, obs.get('Angle', 0), origin='center')
                bx, by = box.exterior.xy
                ax_grid.fill(bx, by, color='gray', alpha=0.5)
                
        # Vẽ đầu dò lên lưới
        valid_colors = mcolors.CSS4_COLORS
        for _, det in st.session_state.det_data.iterrows():
            c = det['Color'].lower()
            use_c = c if c in valid_colors else 'blue'
            ax_grid.plot(det['X'], det['Y'], '^', color=use_c, markersize=8, markeredgecolor='black')

        ax_grid.set_aspect('equal')
        ax_grid.grid(True, linestyle='--', alpha=0.5)
        st.pyplot(fig_grid)
    else:
        st.error("Cần ít nhất 3 điểm (tọa độ) để tạo thành một phòng kín!")
        room_poly = None

with col_input2:
    st.header("2. Vật cản & Bố trí Đầu dò Đa Lớp")
    
    with st.expander("🚧 Danh sách Vật cản (Cylinder / Box)", expanded=True):
        edited_obs = st.data_editor(
            st.session_state.obs_data, num_rows="dynamic", use_container_width=True,
            column_config={"Type": st.column_config.SelectboxColumn("Loại", options=["Cylinder", "Box"])}
        )
        st.session_state.obs_data = edited_obs
        if st.button("🔄 Lưu & Cập nhật Vật cản lên lưới", type="secondary"): st.rerun()

    # NÂNG CẤP CHI TIẾT: CẤU HÌNH TỪNG LỚP KHÍ
    with st.expander("⚙️ Thiết lập Các Lớp Khí & Tự động Bố trí", expanded=True):
        st.write("Kích hoạt và cấu hình thông số cho từng cao độ giám sát:")
        
        active_layers = []
        
        # 1. LỚP KHÍ NHẸ
        use_light = st.checkbox("🌫️ Khí Nhẹ (Giám sát sát trần)", value=True)
        if use_light:
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])
            l_gas = c1.text_input("Tên Khí (VD: CH4)", value="CH4", key="lg")
            l_mod = c2.text_input("Model Đầu dò", value="SD-1", key="lm")
            l_rad = c3.number_input("Bán kính (m)", value=5.0, key="lr")
            l_col = c4.selectbox("Màu hiển thị", ["cyan", "blue", "teal"], key="lc")
            active_layers.append({"layer": "Khí Nhẹ", "gas": l_gas, "model": l_mod, "rad": l_rad, "color": l_col, "z": max(room_z - 0.5, 0.5)})

        # 2. LỚP KHÍ TRUNG BÌNH
        use_mid = st.checkbox("🌬️ Khí Tầm trung (Giám sát vùng thở)", value=False)
        if use_mid:
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])
            m_gas = c1.text_input("Tên Khí (VD: CO)", value="CO", key="mg")
            m_mod = c2.text_input("Model Đầu dò", value="GD-70D", key="mm")
            m_rad = c3.number_input("Bán kính (m)", value=5.0, key="mr")
            m_col = c4.selectbox("Màu hiển thị", ["yellow", "orange", "lime"], key="mc")
            active_layers.append({"layer": "Khí Tầm trung", "gas": m_gas, "model": m_mod, "rad": m_rad, "color": m_col, "z": 1.5})

        # 3. LỚP KHÍ NẶNG
        use_heavy = st.checkbox("☁️ Khí Nặng (Giám sát sát sàn)", value=False)
        if use_heavy:
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])
            h_gas = c1.text_input("Tên Khí (VD: H2S)", value="H2S", key="hg")
            h_mod = c2.text_input("Model Đầu dò", value="SD-3", key="hm")
            h_rad = c3.number_input("Bán kính (m)", value=4.0, key="hr") # Bán kính khí độc thường nhỏ hơn
            h_col = c4.selectbox("Màu hiển thị", ["magenta", "red", "purple"], key="hc")
            active_layers.append({"layer": "Khí Nặng", "gas": h_gas, "model": h_mod, "rad": h_rad, "color": h_col, "z": 0.5})

        if st.button("🚀 Tự động Rải Đầu dò theo cấu hình", type="primary"):
            if not active_layers:
                st.warning("Vui lòng kích hoạt ít nhất 1 lớp khí!")
            elif room_poly is not None:
                new_dets = []
                # Lặp qua từng lớp khí để rải lưới (Cho phép các lớp có số lượng đầu dò khác nhau do bán kính khác nhau)
                for layer in active_layers:
                    spacing = layer["rad"] * 1.5 
                    minx, miny, maxx, maxy = room_poly.bounds
                    nx = max(1, math.ceil((maxx - minx) / spacing))
                    ny = max(1, math.ceil((maxy - miny) / spacing))
                    
                    x_steps = np.linspace(minx + (maxx-minx)/(2*nx), maxx - (maxx-minx)/(2*nx), nx)
                    y_steps = np.linspace(miny + (maxy-miny)/(2*ny), maxy - (maxy-miny)/(2*ny), ny)
                    
                    count = 1
                    for x in x_steps:
                        for y in y_steps:
                            pt = Point(x, y)
                            if room_poly.contains(pt): 
                                new_dets.append({
                                    "ID": f"{layer['model']} ({count:02d})", 
                                    "Gas": f"{layer['gas']} ({layer['layer']})", # Lưu rõ Tên khí + Thuộc tính
                                    "X": round(x, 1), "Y": round(y, 1),
                                    "Z": layer["z"], "Radius": layer["rad"], "Color": layer["color"]
                                })
                                count += 1
                
                st.session_state.det_data = pd.DataFrame(new_dets)
                st.success(f"Đã rải thành công {len(new_dets)} đầu dò!")
                st.rerun()

    st.write("📋 **Bảng Tọa độ Đầu dò (Chỉnh sửa thủ công nếu cần):**")
    edited_dets = st.data_editor(st.session_state.det_data, num_rows="dynamic", use_container_width=True)
    if st.button("🔄 Lưu & Cập nhật Đầu dò lên lưới mặt bằng", type="secondary"): st.rerun()


# ==========================================
# 2. CÁC HÀM LÕI TOÁN HỌC & ĐỒ HỌA
# ==========================================
def create_obstacle_polys(df_obs):
    obs_polys = []
    for _, row in df_obs.iterrows():
        if row['Type'] == 'Cylinder':
            obs_polys.append(Point(row['X'], row['Y']).buffer(row['Width_Radius']))
        elif row['Type'] == 'Box':
            w, l = row['Width_Radius'], row['Length']
            box = Polygon([(row['X']-w/2, row['Y']-l/2), (row['X']+w/2, row['Y']-l/2),
                           (row['X']+w/2, row['Y']+l/2), (row['X']-w/2, row['Y']+l/2)])
            box = affinity.rotate(box, row.get('Angle', 0), origin='center')
            obs_polys.append(box)
    return obs_polys

def check_collision_shapely(df_dets, obs_polys):
    collisions = []
    if not obs_polys or df_dets.empty: return collisions
    for _, det in df_dets.iterrows():
        pt = Point(det['X'], det['Y'])
        if any(poly.contains(pt) for poly in obs_polys):
            collisions.append(det['ID'])
    return collisions

def generate_2d_plot(room_poly, obs_polys, df_dets_group, gas_name):
    minx, miny, maxx, maxy = room_poly.bounds
    res = 0.2
    xx, yy = np.meshgrid(np.arange(minx, maxx, res), np.arange(miny, maxy, res))
    pts_x, pts_y = xx.flatten(), yy.flatten()

    room_path = Path(list(room_poly.exterior.coords))
    in_room_mask = room_path.contains_points(np.c_[pts_x, pts_y])
    
    in_obs_mask = np.zeros(len(pts_x), dtype=bool)
    for obs in obs_polys:
        obs_path = Path(list(obs.exterior.coords))
        in_obs_mask |= obs_path.contains_points(np.c_[pts_x, pts_y])
    
    valid_points_mask = in_room_mask & ~in_obs_mask
    coverage_mask = np.zeros(len(pts_x), dtype=bool)

    for _, det in df_dets_group.iterrows():
        dx, dy, dr = det['X'], det['Y'], det['Radius']
        dist_sq = (pts_x - dx)**2 + (pts_y - dy)**2
        in_radius_mask = dist_sq <= dr**2
        
        check_mask = valid_points_mask & in_radius_mask
        det_pt = Point(dx, dy)
        
        for i in np.where(check_mask)[0]:
            if coverage_mask[i]: continue
            line = LineString([det_pt, Point(pts_x[i], pts_y[i])])
            shadowed = any(line.crosses(obs) for obs in obs_polys)
            if not shadowed: coverage_mask[i] = True

    diem_kha_dung = np.sum(valid_points_mask)
    ty_le = (np.sum(coverage_mask) / diem_kha_dung) * 100 if diem_kha_dung > 0 else 0

    fig, ax = plt.subplots(figsize=(8, 6))
    coverage_2d = coverage_mask.reshape(xx.shape)
    ax.contourf(xx, yy, coverage_2d, levels=[0.5, 1], colors=['#A8E6CF'], alpha=0.6, zorder=1)
    
    rx, ry = room_poly.exterior.xy
    ax.plot(rx, ry, 'k-', lw=3, zorder=2)
    
    for obs in obs_polys:
        ox, oy = obs.exterior.xy
        ax.fill(ox, oy, color='gray', alpha=0.8, zorder=4)

    valid_colors = mcolors.CSS4_COLORS
    for _, det in df_dets_group.iterrows():
        c = det['Color'].lower()
        use_c = c if c in valid_colors else 'blue'
        ax.add_patch(plt.Circle((det['X'], det['Y']), det['Radius'], color=use_c, fill=False, linestyle='--', lw=1.5, zorder=3))
        # Hiển thị tên Model + Tên Khí bên cạnh biểu tượng đầu dò trên đồ thị 2D
        ax.text(det['X']+0.3, det['Y']+0.3, f"{det['ID']}", fontsize=8, color='black', zorder=6, bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))
        ax.plot(det['X'], det['Y'], '^', color=use_c, markersize=12, markeredgecolor='black', zorder=5)

    ax.set_title(f"Hệ thống: {gas_name} | Mức an toàn: {ty_le:.1f}%", fontweight='bold')
    ax.axis('equal'); ax.grid(True, linestyle=':', alpha=0.5)
    return fig, ty_le

def generate_plotly_3d_complex(room_poly, rz, obs_polys, df_obs, df_dets):
    fig = go.Figure()
    rx, ry = room_poly.exterior.xy
    rx, ry = list(rx), list(ry)
    
    fig.add_trace(go.Scatter3d(x=rx, y=ry, z=[0]*len(rx), mode='lines', line=dict(color='white', width=4), name='Đáy tường'))
    fig.add_trace(go.Scatter3d(x=rx, y=ry, z=[rz]*len(rx), mode='lines', line=dict(color='white', width=4), name='Đỉnh tường'))
    for x, y in zip(rx[:-1], ry[:-1]):
        fig.add_trace(go.Scatter3d(x=[x,x], y=[y,y], z=[0,rz], mode='lines', line=dict(color='white', width=2), showlegend=False))

    def get_sphere(x0, y0, z0, r):
        u, v = np.mgrid[0:2*np.pi:15j, 0:np.pi:10j]
        return r*np.cos(u)*np.sin(v)+x0, r*np.sin(u)*np.sin(v)+y0, r*np.cos(v)+z0

    for _, det in df_dets.iterrows():
        # Label 3D hiển thị rõ Tên Khí và Model
        hover_label = f"Model: {det['ID']}<br>Mục tiêu: {det['Gas']}<br>Cao độ Z: {det['Z']}m"
        fig.add_trace(go.Scatter3d(x=[det['X']], y=[det['Y']], z=[det['Z']], mode='markers+text', 
                                   marker=dict(size=6, color='white'), 
                                   text=[det['ID']], textposition="top center", textfont=dict(color="white", size=10),
                                   name=det['ID'], hoverinfo="text", hovertext=hover_label))
        
        sx, sy, sz = get_sphere(det['X'], det['Y'], det['Z'], det['Radius'])
        fig.add_trace(go.Surface(x=sx, y=sy, z=sz, opacity=0.15, showscale=False, colorscale=[[0, det['Color']], [1, det['Color']]]))

    for i, (_, obs) in enumerate(df_obs.iterrows()):
        if obs['Type'] == 'Cylinder':
            z_grid, theta = np.mgrid[0:obs['Height']:2j, 0:2*np.pi:20j]
            fig.add_trace(go.Surface(x=obs['Width_Radius']*np.cos(theta)+obs['X'], y=obs['Width_Radius']*np.sin(theta)+obs['Y'], z=z_grid, opacity=1.0, showscale=False, colorscale='Greys', name="Bồn trụ"))
        elif obs['Type'] == 'Box':
            box_2d = obs_polys[i]
            bx, by = box_2d.exterior.xy
            bx, by = list(bx)[:-1], list(by)[:-1] 
            x_box, y_box = bx * 2, by * 2
            z_box = [0]*4 + [obs['Height']]*4
            ii, jj, kk = [7,0,0,0,4,4,6,6,4,0,3,2], [3,4,1,2,5,6,5,2,0,1,6,3], [0,7,2,3,6,7,1,1,5,5,7,6]
            fig.add_trace(go.Mesh3d(x=x_box, y=y_box, z=z_box, i=ii, j=jj, k=kk, color='gray', opacity=1.0, name="Tủ/Kệ"))

    minx, miny, maxx, maxy = room_poly.bounds
    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[minx, maxx], title='X', backgroundcolor="rgb(30,30,30)", gridcolor="gray"),
            yaxis=dict(range=[miny, maxy], title='Y', backgroundcolor="rgb(30,30,30)", gridcolor="gray"),
            zaxis=dict(range=[0, max(rz, 5)], title='Z', backgroundcolor="rgb(30,30,30)", gridcolor="gray"),
            aspectmode='data'
        ),
        paper_bgcolor="rgb(15,15,15)", plot_bgcolor="rgb(15,15,15)",
        margin=dict(l=0, r=0, b=0, t=30), showlegend=False # Tắt legend vì đã hiện Text Label trực tiếp trên 3D
    )
    return fig

# ==========================================
# 3. WORD REPORT (ĐA LỚP)
# ==========================================
def generate_word_report(figs_dict, img_3d_bytes):
    doc = Document()
    doc.add_heading('BÁO CÁO VÙNG PHỦ KHÍ ĐA LỚP (3D MAPPING)', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('Đơn vị thực hiện: CÔNG TY TNHH CÔNG NGHỆ THIẾT BỊ DÒ KHÍ RIKEN VIET').bold = True
    doc.add_paragraph('_' * 60)
    
    doc.add_heading('1. Phân bổ Không gian 3D Tổng thể', level=1)
    if img_3d_bytes:
        doc.add_picture(img_3d_bytes, width=Inches(6.0))
        doc.add_paragraph('Hình 1: Trực quan hóa cao độ thiết bị và vật cản 3D.').alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_heading('2. Phân tích Điểm mù theo Hệ Khí (Mặt bằng)', level=1)
    for gas_name, fig in figs_dict.items():
        doc.add_heading(f'Hệ thống giám sát: {gas_name}', level=2)
        img_stream = io.BytesIO()
        fig.savefig(img_stream, format='png', bbox_inches='tight', dpi=150)
        img_stream.seek(0)
        doc.add_picture(img_stream, width=Inches(6.0))
        doc.add_paragraph(f'Bản đồ phân tích giao thoa bảo vệ của hệ thống đo {gas_name}.').alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc_stream = io.BytesIO()
    doc.save(doc_stream)
    doc_stream.seek(0)
    return doc_stream

# ==========================================
# 4. TRIGGER KẾT XUẤT
# ==========================================
st.markdown("---")
if st.button("📊 Chạy Mô phỏng Kiến trúc Phức hợp & Tải Báo cáo", use_container_width=True, type='primary'):
    if room_poly is None or edited_dets.empty:
        st.warning("⚠️ Vui lòng nhập đủ tọa độ phòng và danh sách đầu dò!")
    else:
        try:
            obs_polys = create_obstacle_polys(edited_obs)
            
            collided = check_collision_shapely(edited_dets, obs_polys)
            if collided:
                st.error(f"⛔ LỖI VA CHẠM: Đầu dò **{', '.join(collided)}** đang bị đặt nằm bên trong vật cản! Vui lòng chỉnh lại tọa độ X, Y.")
            else:
                with st.spinner('Đang dùng thuật toán Nội suy Raycasting và rà soát bóng mờ đa lớp...'):
                    st.header("3. Phân tích Kết quả Đồ họa")
                    
                    # VẼ 3D
                    fig_3d = generate_plotly_3d_complex(room_poly, room_z, obs_polys, edited_obs, edited_dets)
                    st.plotly_chart(fig_3d, use_container_width=True)
                    
                    img_3d_bytes = io.BytesIO()
                    try:
                        fig_3d.write_image(img_3d_bytes, format='png', width=800, height=500)
                        img_3d_bytes.seek(0)
                    except: img_3d_bytes = None

                    # VẼ 2D TÁCH LỚP
                    gas_groups = edited_dets['Gas'].unique()
                    tabs = st.tabs([f"Bản đồ: {g}" for g in gas_groups])
                    generated_figs = {}
                    
                    for i, gas_name in enumerate(gas_groups):
                        with tabs[i]:
                            df_group = edited_dets[edited_dets['Gas'] == gas_name]
                            fig_2d, coverage = generate_2d_plot(room_poly, obs_polys, df_group, gas_name)
                            st.pyplot(fig_2d)
                            if coverage >= 80:
                                st.success(f"✅ Tỷ lệ bao phủ của {gas_name} đạt chuẩn: {coverage:.1f}%")
                            else:
                                st.warning(f"⚠️ Tỷ lệ bao phủ của {gas_name} chỉ đạt: {coverage:.1f}%")
                            generated_figs[gas_name] = fig_2d
                    
                    # XUẤT WORD
                    word_stream = generate_word_report(generated_figs, img_3d_bytes)
                    st.download_button("📄 Tải Báo cáo Tư vấn Chuyên sâu (Word)", word_stream, "Bao_Cao_RikenViet.docx", type="primary")

        except Exception as e:
            st.error(f"Lỗi hệ thống: {e}. Vui lòng kiểm tra lại tọa độ đa giác hoặc thông số nhập liệu.")

# ==========================================
# 5. FOOTER (BẢN QUYỀN TÁC GIẢ)
# ==========================================
st.markdown("""
    <hr style="border: 0; height: 1px; background-image: linear-gradient(to right, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0)); margin-top: 50px;">
    <div style="text-align: center; color: #888888; font-size: 14px; padding-bottom: 20px;">
        &copy; 2026 All Rights Reserved.<br>
        Designed and programmed by <b>trggiang</b>.
    </div>
""", unsafe_allow_html=True)

