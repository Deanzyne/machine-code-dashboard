import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import itertools

# Page config
st.set_page_config(page_title="G-code Analyzer Dashboard", layout="wide")

# Dark theme CSS
st.markdown(
    """
    <style>
    html, body, [data-testid=\"stAppViewContainer\"] { background-color: #0e1117 !important; color: #e0e0e0 !important; }
    [data-testid=\"stSidebar\"] > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }
    [data-testid=\"stSidebar\"] { background-color: #262730 !important; }
    .stText, .css-1d391kg, .css-12oz5g7 { color: #e0e0e0 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# Title
st.markdown("# 🧠 G-code / MPF Analyzer Dashboard")

# Data source selection
source = st.sidebar.radio("Data Source:", ["Upload G-code/MPF", "Demo: Fibonacci Spiral", "Demo: Dodecahedron"])
if source == "Upload G-code/MPF":
    uploaded_file = st.file_uploader("Upload a .gcode or .mpf file", type=["gcode","mpf","txt"])
    if not uploaded_file:
        st.info("Please upload a .gcode or .mpf file or select a demo to begin.")
        st.stop()
    lines = uploaded_file.read().decode('utf-8').splitlines()
elif source == "Demo: Fibonacci Spiral":
    n = st.sidebar.slider("Fibonacci points", 10, 1000, 200)
    lines = []
    for i in range(n):
        angle = np.deg2rad(137.5 * i)
        r = 0.02 * i
        x = r * np.cos(angle)
        y = r * np.sin(angle)
        z = 0.01 * i
        lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}")
elif source == "Demo: Dodecahedron":
    phi = (1 + np.sqrt(5)) / 2
    a = 1 / phi
    verts = []
    for signs in itertools.product([1, -1], repeat=3):
        verts.append(signs)
    for x, y in itertools.product([1, -1], repeat=2):
        verts.append((0, x*a, y*phi))
        verts.append((x*a, y*phi, 0))
        verts.append((x*phi, 0, y*a))
    lines = []
    for v in verts:
        x, y, z = v
        lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}")

# Parse toolpath lines into numeric data
cols = ['Time Step','X','Y','Z','A','B','C','E','Layer']
data = {c: [] for c in cols}
t, layer_markers, current_layer = 0, 0, -1
for line in lines:
    if ";-----------------------LAYER" in line:
        layer_markers += 1
        m = re.search(r"LAYER\s+(\d+)", line)
        if m: current_layer = int(m.group(1))
    if "G1" in line:
        vals = {ax: None for ax in ['X','Y','Z','A','B','C','E']}
        for ax in vals:
            m = re.search(fr"{ax}([-+]?[0-9]*\.?[0-9]+)", line)
            if m: vals[ax] = float(m.group(1))
        data['Time Step'].append(t)
        data['Layer'].append(current_layer)
        for ax in ['X','Y','Z','A','B','C','E']:
            data[ax].append(vals[ax])
        t += 1
df = pd.DataFrame(data)

# Summary
total_steps = len(df)
unique_layers = sorted(df['Layer'].dropna().unique().astype(int))
total_layers = len(unique_layers)
bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ['X','Y','Z']}
lengths = {ax: bbox[ax][1] - bbox[ax][0] for ax in ['X','Y','Z']}
volume_m3 = np.prod([lengths[ax]/1000 for ax in ['X','Y','Z']])

# Sidebar
st.sidebar.header("📐 Summary & Bounding Box")
st.sidebar.metric("Total Time Steps", total_steps)
st.sidebar.metric("Total Layers", total_layers)
st.sidebar.metric("Layer Markers Found", layer_markers)
st.sidebar.write("**Bounding Box:**")
for ax in ['X','Y','Z']:
    st.sidebar.write(f"- {ax} length: {lengths[ax]:.2f} mm")
st.sidebar.write(f"**Volume:** {volume_m3:.6f} m³")

# Helper for slider ticks
def layer_ticks(min_l, max_l):
    return {f"{i*10}%": int(min_l + (max_l-min_l)*i/10) for i in range(11)}

# Plot template
template = 'plotly_dark'

# 3D Toolpath Visualizer
with st.expander("🌐 3D Toolpath Visualizer (Full Width)", expanded=True):
    mode_type = st.selectbox("Graph Type:", ['Line','Scatter','Streamtube'], help="Line: trajectory, Scatter: points, Streamtube: volumetric flow")
    mode_color = st.selectbox("Visualization Mode:", ['Layer','Extrusion Rate','Distance','Layer Time'])
    show_seams = st.checkbox("Show Layer Seams")
    show_extrema = st.checkbox("Show Layer High/Low")
    show_startstop = st.checkbox("Show Part Start/Stop")

    # Conditional slider
    min_l = unique_layers[0] if unique_layers else 0
    max_l = unique_layers[-1] if unique_layers else 0
    if min_l < max_l:
        layer_range = st.slider("Slice Layer Range:", min_l, max_l, (min_l, max_l), step=1)
        ticks = layer_ticks(min_l, max_l)
        st.markdown(f"**Ticks:** {'  '.join(ticks.keys())}")
    else:
        st.markdown(f"**Only one layer:** {min_l}")
        layer_range = (min_l, max_l)

    df_slice = df[(df['Layer'] >= layer_range[0]) & (df['Layer'] <= layer_range[1])]
    df3 = df_slice.dropna(subset=['X','Y','Z']).sort_values('Time Step')

    # Color mapping
    if mode_color == 'Layer':
        color = df3['Layer']
    elif mode_color == 'Extrusion Rate':
        color = df3['E'].diff().fillna(0)
    elif mode_color == 'Distance':
        coords = df3[['X','Y','Z']].to_numpy()
        d = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        color = pd.Series(np.concatenate([[0], d]), index=df3.index)
    else:
        color = df3.groupby('Layer')['Time Step'].transform('mean')

    # Build trace
    if mode_type == 'Line':
        trace = go.Scatter3d(x=df3['X'], y=df3['Y'], z=df3['Z'],
                             mode='lines', line=dict(color=color, colorscale='Viridis', width=6), showlegend=False)
    elif mode_type == 'Scatter':
        trace = go.Scatter3d(x=df3['X'], y=df3['Y'], z=df3['Z'],
                             mode='markers', marker=dict(color=color, colorscale='Viridis', size=4, opacity=0.6), showlegend=False)
    else:
        # streamtube: use motion vectors as u/v/w
        coords = df3[['X','Y','Z']].to_numpy()
        diffs = np.diff(coords, axis=0)
        u = np.concatenate([diffs[:,0], [0]])
        v = np.concatenate([diffs[:,1], [0]])
        w = np.concatenate([diffs[:,2], [0]])
        trace = go.Streamtube(x=df3['X'], y=df3['Y'], z=df3['Z'],
                              u=u.tolist(), v=v.tolist(), w=w.tolist(),
                              colorscale='Viridis', sizeref=0.5, showlegend=False)

    fig3d = go.Figure(trace)
    # Seams
    if show_seams:
        for _, grp in df3.groupby('Layer'):
            s, e = grp.iloc[0], grp.iloc[-1]
            fig3d.add_trace(go.Scatter3d(x=[s.X,e.X], y=[s.Y,e.Y], z=[s.Z,e.Z],
                                         mode='lines', line=dict(color='white', width=2), showlegend=False))
    # Extremes
    if show_extrema:
        for _, grp in df3.groupby('Layer'):
            hi = grp.loc[grp['Z'].idxmax()]; lo = grp.loc[grp['Z'].idxmin()]
            fig3d.add_trace(go.Scatter3d(x=[hi.X], y=[hi.Y], z=[hi.Z], mode='markers', marker=dict(color='yellow', size=4), showlegend=False))
            fig3d.add_trace(go.Scatter3d(x=[lo.X], y=[lo.Y], z=[lo.Z], mode='markers', marker=dict(color='orange', size=4), showlegend=False))
    # Start/Stop
    if show_startstop and not df3.empty:
        s, e = df3.iloc[0], df3.iloc[-1]
        fig3d.add_trace(go.Scatter3d(x=[s.X], y=[s.Y], z=[s.Z], mode='markers', marker=dict(color='green', size=6), showlegend=False))
        fig3d.add_trace(go.Scatter3d(x=[e.X], y=[e.Y], z=[e.Z], mode='markers', marker=dict(color='red', size=6), showlegend=False))

    fig3d.update_layout(scene=dict(xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)', aspectmode='data'),
                       template=template, height=700, margin=dict(l=0,r=0,b=0,t=0))
    st.plotly_chart(fig3d, use_container_width=False, width=900)

# XYZ Over Time
with st.expander("📈 XYZ Axes Over Time", expanded=True):
    mode_xyz = st.selectbox("XYZ Plot Mode:", ['Raw','Layer Average'], key='xyz_mode')
    xyz_axes = st.multiselect("Select XYZ axes:", ['X','Y','Z'], default=['X','Y','Z'])
    if xyz_axes:
        dfx = df_slice.sort_values('Time Step')
        if mode_xyz == 'Raw':
            fig_xyz = px.line(dfx, x='Time Step', y=xyz_axes, template=template)
        else:
            avg = df_slice.groupby('Layer')[xyz_axes].mean().reset_index()
            fig_xyz = px.line(avg, x='Layer', y=xyz_axes, template=template)
        fig_xyz.update_layout(height=800)
        st.plotly_chart(fig_xyz, use_container_width=False, width=900)

# ABC Over Time
with st.expander("📈 ABC Axes Over Time", expanded=True):
    mode_abc = st.selectbox("ABC Plot Mode:", ['Raw','Layer Average'], key='abc_mode')
    abc_axes = st.multiselect("Select ABC axes:", ['A','B','C'], default=['A','B','C'])
    if abc_axes:
        if mode_abc == 'Raw':
            fig_abc = px.line(dfx, x='Time Step', y=abc_axes, template=template)
        else:
            avg = df_slice.groupby('Layer')[abc_axes].mean().reset_index()
            fig_abc = px.line(avg, x='Layer', y=abc_axes, template=template)
        fig_abc.update_layout(height=500)
        st.plotly_chart(fig_abc, use_container_width=False, width=900)

# Data Table
with st.expander('📄 Data Table & Export', expanded=False):
    st.dataframe(df_slice, use_container_width=True)
    st.download_button('Download CSV', df_slice.to_csv(index=False).encode(), "motion_data.csv", "text/csv")
