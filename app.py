import streamlit as st
import pandas as pd

# --- 1. CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="3D Gas Mapping Tool", layout="wide")
st.title("🛡️ Công cụ Thiết kế Vùng phủ Khí 3D (Gas Mapping)")
st.markdown("**Phát triển nội bộ: Phòng Kỹ thuật** - Nhập thông số để tự động sinh mô hình OpenSCAD.")

# --- 2. GIAO DIỆN NHẬP LIỆU (UI) ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("1. Kích thước không gian (m)")
    room_x = st.number_input("Chiều dài (X)", min_value=1.0, value=15.0, step=1.0)
    room_y = st.number_input("Chiều rộng (Y)", min_value=1.0, value=10.0, step=1.0)
    room_z = st.number_input("Chiều cao trần (Z)", min_value=1.0, value=5.0, step=0.5)

with col2:
    st.subheader("2. Cấu hình Vật cản (Bồn chứa, Tủ điện...)")
    st.info("💡 Có thể thêm/xóa dòng trực tiếp trên bảng. Type: 'Cylinder' (Hình trụ) hoặc 'Cube' (Hình hộp).")
    # Dữ liệu mặc định cho Vật cản
    default_obstacles = pd.DataFrame([
        {"Type": "Cylinder", "X": 7.5, "Y": 5.0, "Width_Radius": 1.5, "Length": 0.0, "Height": 3.5}
    ])
    # Bảng cho phép chỉnh sửa trực tiếp trên Web
    edited_obs = st.data_editor(default_obstacles, num_rows="dynamic", use_container_width=True)

st.subheader("3. Cấu hình Đầu dò khí (Gas Detectors)")
# Dữ liệu mặc định cho Đầu dò
default_detectors = pd.DataFrame([
    {"ID": "SD-1 (01)", "X": 4.0, "Y": 5.0, "Z": 2.0, "Radius": 5.0, "Color": "Cyan"},
    {"ID": "SD-1 (02)", "X": 11.0, "Y": 5.0, "Z": 2.0, "Radius": 5.0, "Color": "Magenta"}
])
edited_dets = st.data_editor(default_detectors, num_rows="dynamic", use_container_width=True)

# --- 3. LÕI XỬ LÝ: HÀM SINH CODE OPENSCAD ---
def generate_scad(rx, ry, rz, df_obs, df_dets):
    scad = f"""// TỰ ĐỘNG SINH BỞI WEB APP
$fn = 100;

// Vẽ khung phòng
module room_frame() {{
    color("Black") {{
        translate([0,0,0]) cylinder(r=0.05, h={rz});
        translate([{rx},0,0]) cylinder(r=0.05, h={rz});
        translate([0,{ry},0]) cylinder(r=0.05, h={rz});
        translate([{rx},{ry},0]) cylinder(r=0.05, h={rz});
        
        hull() {{ translate([0,0,0]) sphere(r=0.05); translate([{rx},0,0]) sphere(r=0.05); }}
        hull() {{ translate([0,0,0]) sphere(r=0.05); translate([0,{ry},0]) sphere(r=0.05); }}
        hull() {{ translate([{rx},{ry},0]) sphere(r=0.05); translate([{rx},0,0]) sphere(r=0.05); }}
        hull() {{ translate([{rx},{ry},0]) sphere(r=0.05); translate([0,{ry},0]) sphere(r=0.05); }}
    }}
}}

// Vẽ danh sách vật cản
module obstacles() {{
"""
    # Vòng lặp quét qua bảng Excel Vật cản trên Web
    for index, row in df_obs.iterrows():
        if row["Type"] == "Cylinder":
            scad += f'    color("DimGray", 1.0) translate([{row["X"]}, {row["Y"]}, 0]) cylinder(r={row["Width_Radius"]}, h={row["Height"]});\n'
        elif row["Type"] == "Cube":
            scad += f'    color("DimGray", 1.0) translate([{row["X"]}, {row["Y"]}, 0]) cube([{row["Width_Radius"]}, {row["Length"]}, {row["Height"]}]);\n'
    
    scad += """}

room_frame();
intersection() {
"""
    scad += f"    cube([{rx}, {ry}, {rz}]);\n"
    scad += "    union() {\n        obstacles();\n\n"

    # Vòng lặp quét qua bảng Excel Đầu dò trên Web
    for index, row in df_dets.iterrows():
        scad += f'        // {row["ID"]}\n'
        scad += f'        color("Red") translate([{row["X"]}, {row["Y"]}, {row["Z"]}]) sphere(r=0.2);\n'
        scad += f'        color("{row["Color"]}", 0.3) difference() {{\n'
        scad += f'            translate([{row["X"]}, {row["Y"]}, {row["Z"]}]) sphere(r={row["Radius"]});\n'
        scad += f'            obstacles();\n        }}\n'

    scad += "    }\n}\n"
    return scad

# --- 4. XUẤT FILE & HIỂN THỊ KẾT QUẢ ---
st.markdown("---")
# Tạo mã SCAD từ dữ liệu bảng
final_scad_code = generate_scad(room_x, room_y, room_z, edited_obs, edited_dets)

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    # Nút Tải file 3D
    st.download_button(
        label="📥 Tải file 3D (.scad)",
        data=final_scad_code,
        file_name="GasMapping_Project.scad",
        mime="text/plain",
        type="primary"
    )

with col_btn2:
    with st.expander("👀 Xem trước mã nguồn OpenSCAD sinh ra"):
        st.code(final_scad_code, language="openscad")