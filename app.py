import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# Page configuration
st.set_page_config(
    page_title="G-code Analyzer Dashboard",
    layout="wide",
)

# Title
st.markdown("# 🧠 G-code / MPF Analyzer Dashboard")

# File uploader
uploaded_file = st.file_uploader(
    "Upload your .gcode or .mpf file",
    type=["gcode", "mpf", "txt"],
)

if uploaded_file:
    # Read and parse file
    lines = uploaded_file.read().decode("utf-8").splitlines()
    data = {axis: [] for axis in ["Time Step", "X", "Y", "Z", "A", "B", "C", "E", "Layer"]}
    current_layer = -1
    t = 0
    for line in lines:
        if ";-----------------------LAYER" in line:
            m = re.search(r"LAYER\s+(\d+)", line)
            if m:
                current_layer = int(m.group(1))
        elif "G1" in line:
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

    # Sidebar controls & metrics
    st.sidebar.header("📐 Summary & Controls")
    total_layers = df["Layer"].nunique(dropna=True)
    bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ["X","Y","Z"]}
    st.sidebar.metric("Total Time Steps", len(df))
    st.sidebar.metric("Total Layers", total_layers)
    st.sidebar.write("**Bounding Box (mm)**")
    for ax in ["X","Y","Z"]:
        mi, ma = bbox[ax]
        st.sidebar.write(f"{ax}: {ma-mi:.2f} (min {mi:.2f}, max {ma:.2f})")

    # Theme switch
    theme = st.sidebar.radio("Theme:", ["Light","Dark"], index=0)
    template = "plotly_white" if theme == "Light" else "plotly_dark"

    # Layer filter
    layers = sorted(df["Layer"].dropna().unique().astype(int))
    selected = st.sidebar.multiselect(
        "Select Layers:", options=layers, default=layers
    )
    filtered = df[df["Layer"].isin(selected)] if selected else df

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 XYZ Axes Over Time")
        xyz = st.multiselect("Axes to plot:", ["X","Y","Z"], default=["X","Y","Z"])
        if xyz:
            df_xyz = filtered.sort_values("Time Step")
            fig_xyz = px.line(
                df_xyz,
                x="Time Step", y=xyz,
                title="Overlay: XYZ Axes",
                labels={"value":"Position (mm)", "variable":"Axis"},
                template=template
            )
            st.plotly_chart(fig_xyz, use_container_width=True)

    with col2:
        st.subheader("📈 ABC Axes Over Time")
        abc = st.multiselect("Axes to plot:", ["A","B","C"], default=["A","B","C"])
        if abc:
            df_abc = filtered.sort_values("Time Step")
            fig_abc = px.line(
                df_abc,
                x="Time Step", y=abc,
                title="Overlay: ABC Axes",
                labels={"value":"Angle (°)", "variable":"Axis"},
                template=template
            )
            st.plotly_chart(fig_abc, use_container_width=True)

    st.markdown("---")
    st.subheader("🌐 3D Toolpath Visualizer")
    df3 = filtered.dropna(subset=["X","Y","Z"]).sort_values("Time Step")
    fig3d = go.Figure(
        data=go.Scatter3d(
            x=df3['X'], y=df3['Y'], z=df3['Z'],
            mode='lines',
            line=dict(color=df3['Layer'], colorscale='Viridis', width=4)
        )
    )
    fig3d.update_layout(
        scene=dict(
            xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)',
            aspectmode='data'
        ),
        template=template,
        margin=dict(l=0, r=0, b=0, t=30)
    )
    st.plotly_chart(fig3d, use_container_width=True)

    st.markdown("---")
    st.subheader("📄 Data Table & Export")
    st.dataframe(filtered, use_container_width=True)
    csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "motion_data.csv", "text/csv")
else:
    st.info("Upload a .gcode or .mpf file to begin analysis.")
