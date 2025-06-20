import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# Page configuration
st.set_page_config(page_title="G-code Analyzer Dashboard", layout="wide")
st.markdown("# 🧠 G-code / MPF Analyzer Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload a .gcode or .mpf file", type=["gcode", "mpf", "txt"])

if uploaded_file:
    # Read file
    content = uploaded_file.read().decode("utf-8")
    lines = content.splitlines()

    # Parse data
    data = {col: [] for col in ["Time Step","X","Y","Z","A","B","C","E","Layer"]}
    layer_count = 0
    current_layer = -1
    t = 0
    for line in lines:
        if ";-----------------------LAYER" in line:
            layer_count += 1
            m = re.search(r"LAYER\s+(\d+)", line)
            if m:
                current_layer = int(m.group(1))
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

    # Sidebar summary & controls
    st.sidebar.header("📐 Summary & Controls")
    total_steps = len(df)
    unique_layers = sorted(df["Layer"].dropna().unique().astype(int))
    total_layers = len(unique_layers)
    bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ["X","Y","Z"]}

    st.sidebar.metric("Total Time Steps", total_steps)
    st.sidebar.metric("Total Layers", total_layers)
    st.sidebar.metric("Layer Markers", layer_count)
    st.sidebar.write("**Bounding Box (mm)**")
    for ax in ["X","Y","Z"]:
        mi, ma = bbox[ax]
        st.sidebar.write(f"{ax}: {ma-mi:.2f}  (min {mi:.2f}, max {ma:.2f})")

    # Theme switcher
    theme = st.sidebar.radio("Theme:", ["Light","Dark"], index=0)
    template = "plotly_white" if theme == "Light" else "plotly_dark"

    # Layer filter
    selected_layers = st.sidebar.multiselect(
        "Select Layers to Include:", options=unique_layers, default=unique_layers
    )
    if selected_layers:
        df_filtered = df[df["Layer"].isin(selected_layers)]
    else:
        df_filtered = df.copy()

    # Main content
    st.subheader("📈 XYZ Axes Over Time")
    xyz_axes = st.multiselect("Axes to Plot:", ["X","Y","Z"], default=["X","Y","Z"])
    if xyz_axes:
        df_xyz = df_filtered.sort_values("Time Step")
        fig_xyz = px.line(
            df_xyz,
            x="Time Step", y=xyz_axes,
            labels={"value":"Position (mm)", "variable":"Axis"},
            title="Overlay: XYZ Axes",
            template=template
        )
        fig_xyz.update_layout(height=600)
        st.plotly_chart(fig_xyz, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns([1,1])

    with col1:
        st.subheader("📈 ABC Axes Over Time")
        abc_axes = st.multiselect("Axes to Plot:", ["A","B","C"], default=["A","B","C"])
        if abc_axes:
            df_abc = df_filtered.sort_values("Time Step")
            fig_abc = px.line(
                df_abc,
                x="Time Step", y=abc_axes,
                labels={"value":"Angle (°)", "variable":"Axis"},
                title="Overlay: ABC Axes",
                template=template
            )
            fig_abc.update_layout(height=400)
            st.plotly_chart(fig_abc, use_container_width=True)

    with col2:
        st.subheader("🌐 3D Toolpath Visualizer with Slice")
        df3 = df_filtered.dropna(subset=["X","Y","Z"]).sort_values("Time Step")
        z_min, z_max = df3["Z"].min(), df3["Z"].max()
        z_slice = st.slider("Slice Height (Z)", float(z_min), float(z_max), float(z_max))
        df_slice = df3[df3["Z"] <= z_slice]
        fig3d = go.Figure(
            data=go.Scatter3d(
                x=df_slice['X'], y=df_slice['Y'], z=df_slice['Z'],
                mode='lines',
                line=dict(color=df_slice['Layer'], colorscale='Viridis', width=4)
            )
        )
        fig3d.update_layout(
            scene=dict(
                xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)',
                aspectmode='data'
            ),
            template=template,
            height=400,
            margin=dict(l=0, r=0, b=0, t=30)
        )
        st.plotly_chart(fig3d, use_container_width=True)

    st.markdown("---")
    st.subheader("📄 Data Table & Export")
    st.dataframe(df_filtered, use_container_width=True)
    csv = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "motion_data.csv", "text/csv")

else:
    st.info("Upload a .gcode or .mpf file to begin analysis.")
