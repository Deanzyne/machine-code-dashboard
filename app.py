import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# Page configuration
st.set_page_config(
    page_title="G-code Analyzer Dashboard",
    layout="wide"
)

# Sidebar: theme switch
theme = st.sidebar.radio("Theme:", ["Light", "Dark"], index=0)
# Inject CSS for day/night mode
if theme == "Dark":
    bg_color = "#0e1117"
    sidebar_color = "#262730"
    text_color = "#e0e0e0"
else:
    bg_color = "#ffffff"
    sidebar_color = "#f0f2f6"
    text_color = "#000000"
st.markdown(
    f"""
    <style>
    [data-testid="stAppViewContainer"] {{ background-color: {bg_color}; color: {text_color}; }}
    [data-testid="stSidebar"] {{ background-color: {sidebar_color}; }}
    .stText {{ color: {text_color}; }}
    </style>
    """,
    unsafe_allow_html=True
)

# Title
st.markdown("# 🧠 G-code / MPF Analyzer Dashboard")

# File uploader
uploaded_file = st.file_uploader(
    "Upload a .gcode or .mpf file", type=["gcode", "mpf", "txt"]
)

if uploaded_file:
    content = uploaded_file.read().decode("utf-8")
    lines = content.splitlines()

    # Parse motion data
    data = {col: [] for col in ["Time Step", "X", "Y", "Z", "A", "B", "C", "E", "Layer"]}
    current_layer = -1
    layer_markers = 0
    t = 0
    for line in lines:
        # Detect layer markers
        if ";-----------------------LAYER" in line:
            layer_markers += 1
            m = re.search(r"LAYER\s+(\d+)", line)
            if m:
                current_layer = int(m.group(1))
        # Motion commands
        if "G1" in line:
            vals = {}
            for ax in ["X","Y","Z","A","B","C","E"]:
                m = re.search(fr"{ax}([-+]?[0-9]*\.?[0-9]+)", line)
                vals[ax] = float(m.group(1)) if m else None
            data["Time Step"].append(t)
            data["Layer"].append(current_layer)
            for ax in ["X","Y","Z","A","B","C","E"]:
                data[ax].append(vals[ax])
            t += 1

    df = pd.DataFrame(data)

    # Sidebar: summary metrics
    total_steps = len(df)
    unique_layers = sorted(df["Layer"].dropna().unique().astype(int))
    total_layers = len(unique_layers)
    bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ["X","Y","Z"]}

    st.sidebar.header("📐 Summary")
    st.sidebar.metric("Total Time Steps", total_steps)
    st.sidebar.metric("Detected Layers", total_layers)
    st.sidebar.metric("Layer Markers Found", layer_markers)
    st.sidebar.write("**Bounding Box (mm)**")
    for ax in ["X","Y","Z"]:
        mi, ma = bbox[ax]
        st.sidebar.write(f"{ax}: {ma-mi:.2f} (min {mi:.2f}, max {ma:.2f})")

    # Sidebar: layer filter
    selected_layers = st.sidebar.slider(
        "Slice by Layer Number", 
        min_value=unique_layers[0] if unique_layers else 0,
        max_value=unique_layers[-1] if unique_layers else 0,
        value=unique_layers[-1] if unique_layers else 0,
        step=1
    )
    df_slice = df[df["Layer"] <= selected_layers]

    # Main: XYZ graph
    st.subheader("📈 XYZ Axes Over Time")
    xyz_axes = st.multiselect(
        "Select XYZ axes to overlay:", ["X","Y","Z"], default=["X","Y","Z"]
    )
    if xyz_axes:
        df_xyz = df.sort_values("Time Step")
        fig_xyz = px.line(
            df_xyz, x="Time Step", y=xyz_axes,
            labels={"value":"Position (mm)", "variable":"Axis"},
            title="Overlay: XYZ Axes",
            template=("plotly_dark" if theme=="Dark" else "plotly_white")
        )
        fig_xyz.update_layout(height=600)
        st.plotly_chart(fig_xyz, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns([1,1])

    # ABC graph
    with col1:
        st.subheader("📈 ABC Axes Over Time")
        abc_axes = st.multiselect(
            "Select ABC axes to overlay:", ["A","B","C"], default=["A","B","C"]
        )
        if abc_axes:
            df_abc = df.sort_values("Time Step")
            fig_abc = px.line(
                df_abc, x="Time Step", y=abc_axes,
                labels={"value":"Angle (°)", "variable":"Axis"},
                title="Overlay: ABC Axes",
                template=("plotly_dark" if theme=="Dark" else "plotly_white")
            )
            fig_abc.update_layout(height=400)
            st.plotly_chart(fig_abc, use_container_width=True)

    # 3D visualizer
    with col2:
        st.subheader("🌐 3D Toolpath Visualizer")
        df3 = df_slice.dropna(subset=["X","Y","Z"]).sort_values("Time Step")
        fig3d = go.Figure(
            go.Scatter3d(
                x=df3['X'], y=df3['Y'], z=df3['Z'],
                mode='lines',
                line=dict(color=df3['Layer'], colorscale='Viridis', width=4)
            )
        )
        fig3d.update_layout(
            scene=dict(
                xaxis_title='X (mm)',
                yaxis_title='Y (mm)',
                zaxis_title='Z (mm)',
                aspectmode='data'
            ),
            template=("plotly_dark" if theme=="Dark" else "plotly_white"),
            height=400,
            margin=dict(l=0, r=0, b=0, t=30)
        )
        st.plotly_chart(fig3d, use_container_width=True)

    st.markdown("---")
    st.subheader("📄 Data Table & Export")
    st.dataframe(df_slice, use_container_width=True)
    csv = df_slice.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "motion_data.csv", "text/csv")
else:
    st.info("Upload a .gcode or .mpf file to begin analysis.")
