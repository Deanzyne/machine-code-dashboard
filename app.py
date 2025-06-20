import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# Page configuration
st.set_page_config(page_title="G-code Analyzer Dashboard", layout="wide")

# Apply dark theme CSS
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0e1117 !important;
        color: #e0e0e0 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #262730 !important;
    }
    .stText, .css-1d391kg, .css-12oz5g7 {
        color: #e0e0e0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Title
st.markdown("# 🧠 G-code / MPF Analyzer Dashboard")

# File uploader
uploaded_file = st.file_uploader(
    "Upload a .gcode or .mpf file", type=["gcode","mpf","txt"]
)
if not uploaded_file:
    st.info("Please upload a .gcode or .mpf file to begin analysis.")
    st.stop()

# Read and parse data
content = uploaded_file.read().decode("utf-8")
lines = content.splitlines()
data = {col: [] for col in ["Time Step","X","Y","Z","A","B","C","E","Layer"]}
t = 0
layer_markers = 0
current_layer = -1
for line in lines:
    if ";-----------------------LAYER" in line:
        layer_markers += 1
        m = re.search(r"LAYER\s+(\d+)", line)
        if m:
            current_layer = int(m.group(1))
    if "G1" in line:
        vals = {ax: None for ax in ["X","Y","Z","A","B","C","E"]}
        for ax in vals:
            m = re.search(fr"{ax}([-+]?[0-9]*\.?[0-9]+)", line)
            if m:
                vals[ax] = float(m.group(1))
        data["Time Step"].append(t)
        data["Layer"].append(current_layer)
        for ax in vals:
            data[ax].append(vals[ax])
        t += 1
# Create DataFrame
df = pd.DataFrame(data)

# Compute summary statistics
total_steps = len(df)
unique_layers = sorted(df["Layer"].dropna().unique().astype(int))
total_layers = len(unique_layers)
bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ["X","Y","Z"]}

# Sidebar: Controls & Summary\with st.sidebar.expander("📐 Controls & Summary", expanded=True):
    st.metric("Total Time Steps", total_steps)
    st.metric("Total Layers", total_layers)
    st.metric("Layer Markers Found", layer_markers)
    st.write("**Bounding Box (mm)**")
    for ax in ["X","Y","Z"]:
        mi, ma = bbox[ax]
        st.write(f"- {ax}: {ma-mi:.2f} (min {mi:.2f}, max {ma:.2f})")
    # Layer range slider
    min_layer = unique_layers[0] if unique_layers else 0
    max_layer = unique_layers[-1] if unique_layers else 0
    layer_range = st.slider(
        "Slice by Layer Range", min_value=min_layer, max_value=max_layer,
        value=(min_layer, max_layer), step=1
    )
# Filter data by layer range
df_slice = df[(df["Layer"] >= layer_range[0]) & (df["Layer"] <= layer_range[1])]

# Plot template for dark theme
template = "plotly_dark"

# Main: XYZ Overlay plot
st.subheader("📈 XYZ Axes Over Time")
xyz_axes = st.multiselect(
    "Select XYZ axes to overlay:", ["X","Y","Z"], default=["X","Y","Z"]
)
if xyz_axes:
    fig_xyz = px.line(
        df_slice.sort_values("Time Step"), x="Time Step", y=xyz_axes,
        labels={"value":"Position (mm)", "variable":"Axis"},
        title="Overlay: XYZ Axes", template=template
    )
    fig_xyz.update_layout(height=600)
    st.plotly_chart(fig_xyz, use_container_width=True)

st.markdown("---")
col1, col2 = st.columns([1,1])

# ABC Overlay plot
with col1:
    st.subheader("📈 ABC Axes Over Time")
    abc_axes = st.multiselect(
        "Select ABC axes to overlay:", ["A","B","C"], default=["A","B","C"]
    )
    if abc_axes:
        fig_abc = px.line(
            df_slice.sort_values("Time Step"), x="Time Step", y=abc_axes,
            labels={"value":"Angle (°)", "variable":"Axis"},
            title="Overlay: ABC Axes", template=template
        )
        fig_abc.update_layout(height=400)
        st.plotly_chart(fig_abc, use_container_width=True)

# 3D Toolpath visualizer plot
with col2:
    st.subheader("🌐 3D Toolpath Visualizer by Layer")
    df3 = df_slice.dropna(subset=["X","Y","Z"]).sort_values("Time Step")
    fig3d = go.Figure(
        go.Scatter3d(
            x=df3['X'], y=df3['Y'], z=df3['Z'], mode='lines',
            line=dict(color=df3['Layer'], colorscale='Viridis', width=4)
        )
    )
    fig3d.update_layout(
        scene=dict(
            xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)',
            aspectmode='data'
        ),
        template=template, height=400,
        margin=dict(l=0,r=0,b=0,t=30)
    )
    st.plotly_chart(fig3d, use_container_width=True)

st.markdown("---")
# Data Table & Export in expander
with st.expander("📄 Data Table & Export", expanded=False):
    st.dataframe(df_slice, use_container_width=True)
    csv = df_slice.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, "motion_data.csv", "text/csv")
