import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re

# Page config
st.set_page_config(page_title="G-code Analyzer Dashboard", layout="wide")

# Dark theme CSS
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] { background-color: #0e1117 !important; color: #e0e0e0 !important; }
    [data-testid="stSidebar"] { background-color: #262730 !important; }
    .stText, .css-1d391kg, .css-12oz5g7 { color: #e0e0e0 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# Title
st.markdown("# 🧠 G-code / MPF Analyzer Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload a .gcode or .mpf file", type=["gcode","mpf","txt"])
if not uploaded_file:
    st.info("Please upload a .gcode or .mpf file to begin.")
    st.stop()

# Read and parse data
lines = uploaded_file.read().decode('utf-8').splitlines()
cols = ['Time Step','X','Y','Z','A','B','C','E','Layer']
data = {c: [] for c in cols}
t, layer_markers, current_layer = 0, 0, -1
for line in lines:
    if ";-----------------------LAYER" in line:
        layer_markers += 1
        m = re.search(r"LAYER\s+(\d+)", line)
        if m:
            current_layer = int(m.group(1))
    if "G1" in line:
        vals = {ax: None for ax in ['X','Y','Z','A','B','C','E']}
        for ax in vals:
            m = re.search(fr"{ax}([-+]?[0-9]*\.?[0-9]+)", line)
            if m:
                vals[ax] = float(m.group(1))
        data['Time Step'].append(t)
        data['Layer'].append(current_layer)
        for ax in ['X','Y','Z','A','B','C','E']:
            data[ax].append(vals[ax])
        t += 1
df = pd.DataFrame(data)

# Summary statistics
total_steps = len(df)
unique_layers = sorted(df['Layer'].dropna().unique().astype(int))
total_layers = len(unique_layers)
bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ['X','Y','Z']}
# lengths in mm
lengths = {ax: bbox[ax][1] - bbox[ax][0] for ax in ['X','Y','Z']}
# volume in m^3
volume_m3 = np.prod([lengths[ax] / 1000 for ax in ['X','Y','Z']])

# Sidebar: summary & bounding box
st.sidebar.header("📐 Summary & Bounding Box")
st.sidebar.metric("Total Time Steps", total_steps)
st.sidebar.metric("Total Layers", total_layers)
st.sidebar.metric("Layer Markers Found", layer_markers)
st.sidebar.write("**Bounding Box:**")
for ax in ['X','Y','Z']:
    st.sidebar.write(f"- {ax} length: {lengths[ax]:.2f} mm")
st.sidebar.write(f"**Volume:** {volume_m3:.6f} m³")

# 3D bounding box visualizer in sidebar
bx, by, bz = bbox['X'], bbox['Y'], bbox['Z']
corners = [[bx[i], by[j], bz[k]] for i in range(2) for j in range(2) for k in range(2)]
edges = [(0,1),(0,2),(0,4),(1,3),(1,5),(2,3),(2,6),(3,7),(4,5),(4,6),(5,7),(6,7)]
fig_bb = go.Figure()
for e in edges:
    x0,y0,z0 = corners[e[0]]
    x1,y1,z1 = corners[e[1]]
    fig_bb.add_trace(go.Scatter3d(
        x=[x0,x1], y=[y0,y1], z=[z0,z1],
        mode='lines', line=dict(color='lightgray', width=2), showlegend=False
    ))
# Annotate X dimension on one edge
mid_x = (bx[0] + bx[1]) / 2
fig_bb.add_trace(go.Scatter3d(
    x=[mid_x], y=[by[0]], z=[bz[0]],
    mode='text', text=[f"X: {lengths['X']:.2f} mm"], textposition='bottom center', showlegend=False
))
fig_bb.update_layout(
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(visible=False),
        aspectmode='data'
    ),
    template='plotly_dark', height=250, margin=dict(l=0, r=0, b=0, t=0)
)
st.sidebar.plotly_chart(fig_bb, use_container_width=True)

# Layer range slider
min_layer = unique_layers[0] if unique_layers else 0
max_layer = unique_layers[-1] if unique_layers else 0
layer_range = st.sidebar.slider("Select Layer Range:", min_layer, max_layer, (min_layer, max_layer), step=1)
# Filtered data
df_slice = df[(df['Layer'] >= layer_range[0]) & (df['Layer'] <= layer_range[1])]

# Plot template
template = 'plotly_dark'

# 3D Toolpath Visualizer (full width)
with st.expander("🌐 3D Toolpath Visualizer (Full Width)", expanded=True):
    mode3d = st.selectbox("Color by:", ['Layer','Time Step','Avg Layer Speed','Extrusion'])
    df3 = df_slice.dropna(subset=['X','Y','Z']).sort_values('Time Step')
    if mode3d == 'Layer':
        color = df3['Layer']
    elif mode3d == 'Time Step':
        color = df3['Time Step']
    elif mode3d == 'Avg Layer Speed':
        coords = df3[['X','Y','Z']].to_numpy()
        d = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        speeds = np.concatenate([[0], d])
        layer_speed = df3.groupby('Layer')['speed'].transform(lambda x: x.mean()) if 'speed' in df3 else speeds
        color = layer_speed
    else:
        color = df3['E'].diff().fillna(0)
    fig3d = go.Figure(
        go.Scatter3d(
            x=df3['X'], y=df3['Y'], z=df3['Z'], mode='lines',
            line=dict(color=color, colorscale='Viridis', width=6)
        )
    )
    fig3d.update_layout(
        scene=dict(xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)', aspectmode='data'),
        template=template, height=700, margin=dict(l=0, r=0, b=0, t=0)
    )
    st.plotly_chart(fig3d, use_container_width=True)

# XYZ Axes Over Time
with st.expander("📈 XYZ Axes Over Time", expanded=True):
    mode_xyz = st.selectbox("XYZ Plot Mode:", ['Raw','Layer Average'], key='xyz_mode')
    xyz_axes = st.multiselect("Select XYZ axes:", ['X','Y','Z'], default=['X','Y','Z'])
    if xyz_axes:
        if mode_xyz == 'Raw':
            fig_xyz = px.line(df_slice.sort_values('Time Step'), x='Time Step', y=xyz_axes, template=template)
        else:
            avg = df_slice.groupby('Layer')[xyz_axes].mean().reset_index()
            fig_xyz = px.line(avg, x='Layer', y=xyz_axes, template=template)
        fig_xyz.update_layout(height=500)
        st.plotly_chart(fig_xyz, use_container_width=True)

# ABC Axes Over Time
with st.expander("📈 ABC Axes Over Time", expanded=True):
    mode_abc = st.selectbox("ABC Plot Mode:", ['Raw','Layer Average'], key='abc_mode')
    abc_axes = st.multiselect("Select ABC axes:", ['A','B','C'], default=['A','B','C'])
    if abc_axes:
        if mode_abc == 'Raw':
            fig_abc = px.line(df_slice.sort_values('Time Step'), x='Time Step', y=abc_axes, template=template)
        else:
            avg = df_slice.groupby('Layer')[abc_axes].mean().reset_index()
            fig_abc = px.line(avg, x='Layer', y=abc_axes, template=template)
        fig_abc.update_layout(height=500)
        st.plotly_chart(fig_abc, use_container_width=True)

# Data Table & Export
with st.expander('📄 Data Table & Export', expanded=False):
    st.dataframe(df_slice, use_container_width=True)
    csv = df_slice.to_csv(index=False).encode('utf-8')
    st.download_button('Download CSV', csv, 'motion_data.csv', 'text/csv')
