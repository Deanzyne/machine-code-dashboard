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
source = st.sidebar.radio("Data Source:", ["Upload G-code/MPF", "Demo: Fibonacci Spiral", "Demo: Dodecahedron"], key='source')
if source == "Upload G-code/MPF":
    uploaded_file = st.file_uploader("Upload a .gcode or .mpf file", type=["gcode","mpf","txt"], key='file_uploader')
    if not uploaded_file:
        st.info("Please upload a .gcode or .mpf file or select a demo to begin.")
        st.stop()
    lines = uploaded_file.read().decode('utf-8').splitlines()
elif source == "Demo: Fibonacci Spiral":
    n = st.sidebar.slider("Fibonacci points", 10, 1000, 200, key='fib_points')
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
    lines = [f"G1 X{v[0]:.3f} Y{v[1]:.3f} Z{v[2]:.3f}" for v in verts]

# Parse lines into DataFrame
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

# Summary metrics
total_steps = len(df)
unique_layers = sorted(df['Layer'].dropna().unique().astype(int))
total_layers = len(unique_layers)
bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ['X','Y','Z']}
lengths = {ax: bbox[ax][1] - bbox[ax][0] for ax in ['X','Y','Z']}
volume_m3 = np.prod([lengths[ax]/1000 for ax in ['X','Y','Z']])

def layer_ticks(min_l, max_l):
    return {f"{i*10}%": int(min_l + (max_l-min_l)*i/10) for i in range(11)}

# Sidebar summary
st.sidebar.header("📐 Summary & Bounding Box")
st.sidebar.metric("Total Time Steps", total_steps)
st.sidebar.metric("Total Layers", total_layers)
st.sidebar.metric("Layer Markers Found", layer_markers)
st.sidebar.write("**Bounding Box:**")
for ax in ['X','Y','Z']:
    st.sidebar.write(f"- {ax} length: {lengths[ax]:.2f} mm")
st.sidebar.write(f"**Volume:** {volume_m3:.6f} m³")

# Plot template
template = 'plotly_dark'

# 3D Visualizer with animation incorporating checkboxes
with st.expander("🌐 3D Toolpath Visualizer (Full Width)", expanded=True):
    c1, c2, c3, c4 = st.columns([3,3,1,1])
    graph_type = c1.selectbox("Graph Type:", ['Line','Scatter','Streamtube'], key='graph_type')
    vis_mode = c2.selectbox("Visualization Mode:", ['Layer','Extrusion Rate','Distance','Layer Time'], key='vis_mode')
    show_seams = c3.checkbox("Show Layer Seams", value=False, key='seams')
    show_extrema = c3.checkbox("Show Layer High/Low", value=False, key='extrema')
    show_startstop = c3.checkbox("Show Part Start/Stop", value=False, key='startstop')
    animate_btn = c4.button("Animate 10s", key='animate')

    # Layer range slider + ticks
    min_l = unique_layers[0] if unique_layers else 0
    max_l = unique_layers[-1] if unique_layers else 0
    layer_range = st.slider("Slice Layer Range:", min_l, max_l, (min_l, max_l), step=1, key='slice_range')
    ticks = layer_ticks(min_l, max_l)
    cols_ticks = st.columns(len(ticks))
    for idx, (lbl, val) in enumerate(ticks.items()):
        cols_ticks[idx].caption(f"{lbl}\n{val}")

    df_slice = df[(df['Layer'] >= layer_range[0]) & (df['Layer'] <= layer_range[1])]
    df3 = df_slice.dropna(subset=['X','Y','Z']).sort_values('Time Step')

    # Color mapping
    if vis_mode=='Layer': color = df3['Layer']
    elif vis_mode=='Extrusion Rate': color = df3['E'].diff().fillna(0)
    elif vis_mode=='Distance':
        coords = df3[['X','Y','Z']].to_numpy()
        d = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        color = pd.Series(np.concatenate([[0], d]), index=df3.index)
    else:
        color = df3.groupby('Layer')['Time Step'].transform('mean')

    # Build base trace
    if graph_type=='Line':
        base = go.Scatter3d(x=df3['X'], y=df3['Y'], z=df3['Z'], mode='lines', line=dict(color=color, colorscale='Viridis', width=6))
    elif graph_type=='Scatter':
        base = go.Scatter3d(x=df3['X'], y=df3['Y'], z=df3['Z'], mode='markers', marker=dict(color=color, colorscale='Viridis', size=4, opacity=0.6))
    else:
        u = np.concatenate([[0], np.diff(df3['X'])])
        v = np.concatenate([[0], np.diff(df3['Y'])])
        w = np.concatenate([[0], np.diff(df3['Z'])])
        base = go.Streamtube(x=df3['X'], y=df3['Y'], z=df3['Z'], u=u, v=v, w=w, colorscale='Viridis', sizeref=0.5)

    # Prepare figure
    if animate_btn:
        N = 120
        frame_dur = int(10000/N)
        frames = []
        total = len(df3)
        for i, frac in enumerate(np.linspace(1/N,1,N)):
            cut = int(frac*total)
            part = df3.iloc[:cut]
            theta = 2*np.pi*frac
            eye = dict(x=2*np.cos(theta), y=2*np.sin(theta), z=1)
            traces = []
            if graph_type=='Line':
                traces.append(go.Scatter3d(x=part['X'], y=part['Y'], z=part['Z'], mode='lines', line=dict(color=color.iloc[:cut], colorscale='Viridis', width=6)))
            elif graph_type=='Scatter':
                traces.append(go.Scatter3d(x=part['X'], y=part['Y'], z=part['Z'], mode='markers', marker=dict(color=color.iloc[:cut], colorscale='Viridis', size=4, opacity=0.6)))
            else:
                u2 = np.concatenate([[0], np.diff(part['X'])])
                v2 = np.concatenate([[0], np.diff(part['Y'])])
                w2 = np.concatenate([[0], np.diff(part['Z'])])
                traces.append(go.Streamtube(x=part['X'], y=part['Y'], z=part['Z'], u=u2, v=v2, w=w2, colorscale='Viridis', sizeref=0.5))
            # add overlays per checkbox
            if show_seams:
                for _, g in part.groupby('Layer'):
                    s0,e0 = g.iloc[0], g.iloc[-1]
                    traces.append(go.Scatter3d(x=[s0.X,e0.X], y=[s0.Y,e0.Y], z=[s0.Z,e0.Z], mode='lines', line=dict(color='white', width=2), showlegend=False))
            if show_extrema:
                for _, g in part.groupby('Layer'):
                    hi = g.loc[g['Z'].idxmax()]
                    lo = g.loc[g['Z'].idxmin()]
                    traces.append(go.Scatter3d(x=[hi.X], y=[hi.Y], z=[hi.Z], mode='markers', marker=dict(color='yellow', size=4), showlegend=False))
                    traces.append(go.Scatter3d(x=[lo.X], y=[lo.Y], z=[lo.Z], mode='markers', marker=dict(color='orange', size=4), showlegend=False))
            if show_startstop and not part.empty:
                spt = part.iloc[0]; ept = part.iloc[-1]
                traces.append(go.Scatter3d(x=[spt.X], y=[spt.Y], z=[spt.Z], mode='markers', marker=dict(color='green', size=6), showlegend=False))
                traces.append(go.Scatter3d(x=[ept.X], y=[ept.Y], z=[ept.Z], mode='markers', marker=dict(color='red', size=6), showlegend=False))
            frames.append(go.Frame(data=traces, name=f'f{i}', layout=dict(scene_camera=dict(eye=eye))))
        fig3d = go.Figure(data=[base], frames=frames)
        fig3d.update_layout(updatemenus=[dict(type='buttons', showactive=False, buttons=[dict(label='▶️ Play', method='animate', args=[None, dict(frame=dict(duration=frame_dur, redraw=True), transition=dict(duration=0), fromcurrent=True)])])])
    else:
        fig3d = go.Figure(data=[base])
        # overlays static
        if show_seams:
            for _, g in df3.groupby('Layer'):
                s0,e0 = g.iloc[0], g.iloc[-1]
                fig3d.add_trace(go.Scatter3d(x=[s0.X,e0.X], y=[s0.Y,e0.Y], z=[s0.Z,e0.Z], mode='lines', line=dict(color='white', width=2), showlegend=False))
        if show_extrema:
            for _, g in df3.groupby('Layer'):
                hi = g.loc[g['Z'].idxmax()]; lo = g.loc[g['Z'].idxmin()]
                fig3d.add_trace(go.Scatter3d(x=[hi.X], y=[hi.Y], z=[hi.Z], mode='markers', marker=dict(color='yellow', size=4), showlegend=False))
                fig3d.add_trace(go.Scatter3d(x=[lo.X], y=[lo.Y], z=[lo.Z], mode='markers', marker=dict(color='orange', size=4), showlegend=False))
        if show_startstop and not df3.empty:
            spt, ept = df3.iloc[0], df3.iloc[-1]
            fig3d.add_trace(go.Scatter3d(x=[spt.X], y=[spt.Y], z=[spt.Z], mode='markers', marker=dict(color='green', size=6), showlegend=False))
            fig3d.add_trace(go.Scatter3d(x=[ept.X], y=[ept.Y], z=[ept.Z], mode='markers', marker=dict(color='red', size=6), showlegend=False))

    fig3d.update_layout(scene=dict(xaxis_title='X (mm)', yaxis_title='Y (mm)', zaxis_title='Z (mm)', aspectmode='data'), template=template, height=700, margin=dict(l=0,r=0,b=0,t=0))
    st.plotly_chart(fig3d, use_container_width=False, width=900)

    # Download HTML
    if animate_btn:
        html = fig3d.to_html(include_plotlyjs='cdn')
        st.download_button('Download Animation (HTML)', html, file_name='animation.html', mime='text/html')

# XYZ Over Time
with st.expander("📈 XYZ Axes Over Time", expanded=True):
    mode_xyz = st.selectbox("XYZ Plot Mode:", ['Raw','Layer Average'], key='xyz_mode2')
    xyz_axes = st.multiselect("Select XYZ axes:", ['X','Y','Z'], default=['X','Y','Z'], key='xyz_axes')
    if xyz_axes:
        dfx = df_slice.sort_values('Time Step')
        if mode_xyz=='Raw':
            fig_xyz = px.line(dfx, x='Time Step', y=xyz_axes, template=template)
        else:
            avg = df_slice.groupby('Layer')[xyz_axes].mean().reset_index()
            fig_xyz = px.line(avg, x='Layer', y=xyz_axes, template=template)
        fig_xyz.update_layout(height=800)
        st.plotly_chart(fig_xyz, use_container_width=False, width=900)

# ABC Over Time
with st.expander("📈 ABC Axes Over Time", expanded=True):
    mode_abc = st.selectbox("ABC Plot Mode:", ['Raw','Layer Average'], key='abc_mode2')
    abc_axes = st.multiselect("Select ABC axes:", ['A','B','C'], default=['A','B','C'], key='abc_axes')
    if abc_axes:
        dfx = df_slice.sort_values('Time Step')
        if mode_abc=='Raw':
            fig_abc = px.line(dfx, x='Time Step', y=abc_axes, template=template)
        else:
            avg = df_slice.groupby('Layer')[abc_axes].mean().reset_index()
            fig_abc = px.line(avg, x='Layer', y=abc_axes, template=template)
        fig_abc.update_layout(height=500)
        st.plotly_chart(fig_abc, use_container_width=False, width=900)

# Data Table & Export
with st.expander('📄 Data Table & Export', expanded=False):
    st.dataframe(df_slice, use_container_width=True)
    st.download_button('Download CSV', df_slice.to_csv(index=False).encode(), 'motion_data.csv', 'text/csv')
