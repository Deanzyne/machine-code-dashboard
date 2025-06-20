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
    html, body, [data-testid="stAppViewContainer"] {background-color: #0e1117 !important; color: #e0e0e0 !important;}
    [data-testid="stSidebar"] {background-color: #262730 !important;}
    .stText, .css-1d391kg, .css-12oz5g7 {color: #e0e0e0 !important;}
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("# 🧠 G-code / MPF Analyzer Dashboard")

# Upload
uploaded_file = st.file_uploader("Upload .gcode/.mpf file", type=["gcode","mpf","txt"])
if not uploaded_file:
    st.info("Please upload a .gcode or .mpf file to begin.")
    st.stop()

# Parse file
lines = uploaded_file.read().decode('utf-8').splitlines()
cols = ["Time Step","X","Y","Z","A","B","C","E","Layer"]
data = {c: [] for c in cols}
t, layer_markers, current_layer = 0, 0, -1
for line in lines:
    if ";-----------------------LAYER" in line:
        layer_markers += 1
        m = re.search(r"LAYER\s+(\d+)", line)
        if m: current_layer = int(m.group(1))
    if "G1" in line:
        vals = {ax: None for ax in list("XYZABC E".split()) if ax!=' '}
        for ax in ['X','Y','Z','A','B','C','E']:
            m = re.search(fr"{ax}([-+]?[0-9]*\.?[0-9]+)", line)
            if m: vals[ax] = float(m.group(1))
        data['Time Step'].append(t)
        data['Layer'].append(current_layer)
        for ax in ['X','Y','Z','A','B','C','E']:
            data[ax].append(vals.get(ax))
        t+=1

# DataFrame
df = pd.DataFrame(data)
# Summary
total_steps = len(df)
unique_layers = sorted(df['Layer'].dropna().unique().astype(int))
total_layers = len(unique_layers)
bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ['X','Y','Z']}
volume = np.prod([bbox[ax][1]-bbox[ax][0] for ax in ['X','Y','Z']])

# Sidebar controls (always visible)
st.sidebar.header("📐 Controls & Summary")
st.sidebar.metric("Total Time Steps", total_steps)
st.sidebar.metric("Total Layers", total_layers)
st.sidebar.metric("Layer Markers Found", layer_markers)
st.sidebar.write("**Bounding Box (mm)**")
for ax in ['X','Y','Z']:
    mi, ma = bbox[ax]
    st.sidebar.write(f"- {ax}: {ma-mi:.2f} (min {mi:.2f}, max {ma:.2f})")
st.sidebar.write(f"**Volume:** {volume:.2f} mm³")

# 3D bounding box visualizer
bx, by, bz = bbox['X'], bbox['Y'], bbox['Z']
corners = [ [bx[i], by[j], bz[k]] for i in range(2) for j in range(2) for k in range(2) ]
edges = [ (0,1),(0,2),(0,4),(1,3),(1,5),(2,3),(2,6),(3,7),(4,5),(4,6),(5,7),(6,7) ]
fig_bb = go.Figure()
for e in edges:
    x0,y0,z0 = corners[e[0]]
    x1,y1,z1 = corners[e[1]]
    fig_bb.add_trace(go.Scatter3d(x=[x0,x1], y=[y0,y1], z=[z0,z1], mode='lines', line=dict(color='white', width=2)))
fig_bb.update_layout(title='Bounding Box', scene=dict(aspectmode='data'), template='plotly_dark', height=300, margin=dict(l=0,r=0,b=0,t30))
st.sidebar.plotly_chart(fig_bb, use_container_width=True)

# Layer slice
min_layer = unique_layers[0] if unique_layers else 0
max_layer = unique_layers[-1] if unique_layers else 0
layer_range = st.sidebar.slider("Slice by Layer Range", min_layer, max_layer, (min_layer,max_layer))
df_slice = df[(df['Layer']>=layer_range[0])&(df['Layer']<=layer_range[1])]

template='plotly_dark'

# Modes for XYZ/ABC
mode_xyz = st.selectbox("XYZ Plot Mode", ['Raw','Layer Average'])
mode_abc = st.selectbox("ABC Plot Mode", ['Raw','Layer Average'])

# Plot layout
st.subheader("📈 XYZ Axes Over Time")
xyz_axes = st.multiselect("Select XYZ axes:",["X","Y","Z"],default=["X","Y","Z"])
if xyz_axes:
    if mode_xyz=='Raw':
        fig=px.line(df_slice.sort_values('Time Step'), x='Time Step', y=xyz_axes, template=template, labels={'value':'Position','variable':'Axis'})
    else:
        avg = df_slice.groupby('Layer')[xyz_axes].mean().reset_index()
        fig=px.line(avg, x='Layer', y=xyz_axes, template=template, labels={'value':'Avg Position','variable':'Axis'})
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)

st.markdown('---')
col1,col2=st.columns([1,2])
with col1:
    st.subheader("📈 ABC Axes Over Time")
    abc_axes=st.multiselect("Select ABC axes:",["A","B","C"],default=["A","B","C"])
    if abc_axes:
        if mode_abc=='Raw':
            fig=px.line(df_slice.sort_values('Time Step'), x='Time Step', y=abc_axes, template=template, labels={'value':'Angle','variable':'Axis'})
        else:
            avg=df_slice.groupby('Layer')[abc_axes].mean().reset_index()
            fig=px.line(avg,x='Layer',y=abc_axes,template=template,labels={'value':'Avg Angle','variable':'Axis'})
        fig.update_layout(height=300)
        st.plotly_chart(fig,use_container_width=True)
with col2:
    st.subheader("🌐 3D Toolpath Visualizer Modes")
    mode3d=st.selectbox("Color by:",['Layer','Time','Avg Layer Speed','Extrusion'])
    df3=df_slice.dropna(subset=['X','Y','Z']).sort_values('Time Step')
    if mode3d=='Layer':
        color=df3['Layer']
    elif mode3d=='Time':
        color=df3['Time Step']
    elif mode3d=='Avg Layer Speed':
        # compute speeds
        coords=df3[['X','Y','Z']].to_numpy()
        d=np.linalg.norm(np.diff(coords,axis=0),axis=1)
        speeds=np.concatenate([[0],d])
        df3['speed']=speeds
        layer_speed=df3.groupby('Layer')['speed'].transform('mean')
        color=layer_speed
    else:
        extr=df3['E'].diff().fillna(0)
        color=extr
    fig3d=go.Figure(go.Scatter3d(x=df3['X'],y=df3['Y'],z=df3['Z'],mode='lines',line=dict(color=color,colorscale='Viridis',width=4)))
    fig3d.update_layout(scene=dict(xaxis_title='X',yaxis_title='Y',zaxis_title='Z',aspectmode='data'),template=template,height=600,margin=dict(l=0,r=0,b=0,t30))
    st.plotly_chart(fig3d,use_container_width=True)

st.markdown('---')
# Data expander
with st.expander('📄 Data Table & Export',expanded=False):
    st.dataframe(df_slice,use_container_width=True)
    st.download_button('Download CSV',df_slice.to_csv(index=False).encode(),"motion_data.csv","text/csv")
