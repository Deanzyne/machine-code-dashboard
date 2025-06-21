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
data_src = st.sidebar.radio("Data Source:", ["Upload G-code/MPF", "Demo: Fibonacci Spiral", "Demo: Dodecahedron"], key='source')
if data_src == "Upload G-code/MPF":
    uploaded = st.file_uploader("Upload a .gcode or .mpf file", type=["gcode","mpf","txt"], key='file')
    if not uploaded:
        st.info("Please upload a file or select a demo.")
        st.stop()
    lines = uploaded.read().decode('utf-8').splitlines()
elif data_src == "Demo: Fibonacci Spiral":
    pts = st.sidebar.slider("Fibonacci points", 10, 1000, 200, key='fib')
    lines = []
    for i in range(pts):
        ang = np.deg2rad(137.5 * i)
        r = 0.02 * i
        x, y, z = r*np.cos(ang), r*np.sin(ang), 0.01*i
        lines.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}")
else:
    phi = (1 + np.sqrt(5)) / 2; a = 1/phi
    verts = []
    for s in itertools.product([1,-1], repeat=3): verts.append(s)
    for x,y in itertools.product([1,-1], repeat=2):
        verts.extend([(0,x*a,y*phi),(x*a,y*phi,0),(x*phi,0,y*a)])
    lines = [f"G1 X{v[0]:.3f} Y{v[1]:.3f} Z{v[2]:.3f}" for v in verts]

# Parse into DataFrame
cols = ['Time Step','X','Y','Z','A','B','C','E','Layer']
data = {c: [] for c in cols}
t, markers, curr = 0, 0, -1
for ln in lines:
    if ";-----------------------LAYER" in ln:
        markers += 1
        m = re.search(r"LAYER\s+(\d+)", ln)
        if m: curr = int(m.group(1))
    if "G1" in ln:
        vals = {ax: None for ax in ['X','Y','Z','A','B','C','E']}
        for ax in vals:
            m = re.search(fr"{ax}([-+]?[0-9]*\.?[0-9]+)", ln)
            if m: vals[ax] = float(m.group(1))
        data['Time Step'].append(t)
        data['Layer'].append(curr)
        for ax in vals: data[ax].append(vals[ax])
        t += 1

df = pd.DataFrame(data)

# Summary metrics
steps = len(df)
ulayers = sorted(df['Layer'].dropna().unique().astype(int))
bbox = {ax: (df[ax].min(), df[ax].max()) for ax in ['X','Y','Z']}
lengths = {ax: mx-mn for ax,(mn,mx) in bbox.items()}
vol = np.prod([lengths[ax]/1000 for ax in lengths])

# Sidebar summary
st.sidebar.header("📐 Summary & Bounding Box")
st.sidebar.metric("Total Time Steps", steps)
st.sidebar.metric("Total Layers", len(ulayers))
st.sidebar.metric("Layer Markers Found", markers)
st.sidebar.write("**Bounding Box:**")
for ax in ['X','Y','Z']: st.sidebar.write(f"- {ax} length: {lengths[ax]:.2f} mm")
st.sidebar.write(f"**Volume:** {vol:.6f} m³")

# Helper
def layer_ticks(minl, maxl): return {f"{i*10}%": int(minl + (maxl-minl)*i/10) for i in range(11)}

# 3D Toolpath Visualizer
with st.expander("🌐 3D Toolpath Visualizer", expanded=True):
    c1,c2,c3,c4,c5 = st.columns([3,3,1,2,2])
    gtype = c1.selectbox("Graph Type:", ['Line','Scatter','Streamtube'], key='gtype')
    vmode = c2.selectbox("Visualization Mode:", ['Layer','Extrusion Rate','Distance','Layer Time'], key='vmode')
    show_seams = c3.checkbox("Show Layer Seams", key='s1')
    show_ext = c3.checkbox("Show Layer High/Low", key='s2')
    show_ss   = c3.checkbox("Show Part Start/Stop", key='s3')
    samp = c4.slider("Simplify Every Nth Point", 1, 100, 1, key='samp')
    anim = c5.button("Animate 10s", key='anim')

    minl, maxl = ulayers[0] if ulayers else 0, ulayers[-1] if ulayers else 0
    lr = st.slider("Slice Layer Range:", minl, maxl, (minl,maxl), key='lr')
    ticks = layer_ticks(minl,maxl)
    cols = st.columns(len(ticks))
    for i,(lbl,val) in enumerate(ticks.items()): cols[i].caption(f"{lbl}\n{val}")

    df_slice = df[(df['Layer']>=lr[0])&(df['Layer']<=lr[1])]
    df3 = df_slice.dropna(subset=['X','Y','Z']).reset_index(drop=True)
    if samp>1: df3 = df3.iloc[::samp].reset_index(drop=True)

    # color map
    if vmode=='Layer': color=df3['Layer']
    elif vmode=='Extrusion Rate': color=df3['E'].diff().fillna(0)
    elif vmode=='Distance':
        coords=df3[['X','Y','Z']].to_numpy(); d=np.linalg.norm(np.diff(coords,axis=0),axis=1)
        color=pd.Series(np.concatenate([[0],d]),index=df3.index)
    else: color=df3.groupby('Layer')['Time Step'].transform('mean')

    def make_traces(df_part):
        if gtype=='Line': return [go.Scatter3d(x=df_part['X'],y=df_part['Y'],z=df_part['Z'],mode='lines',line=dict(color=color.loc[df_part.index],colorscale='Viridis',width=6))]
        if gtype=='Scatter': return [go.Scatter3d(x=df_part['X'],y=df_part['Y'],z=df_part['Z'],mode='markers',marker=dict(color=color.loc[df_part.index],colorscale='Viridis',size=4,opacity=0.6))]
        u,v,w = np.concatenate([[0],np.diff(df_part['X'])]), np.concatenate([[0],np.diff(df_part['Y'])]), np.concatenate([[0],np.diff(df_part['Z'])])
        return [go.Streamtube(x=df_part['X'],y=df_part['Y'],z=df_part['Z'],u=u,v=v,w=w,colorscale='Viridis',sizeref=0.5)]

    # static or animated
    if anim:
        N=120; fd=int(10000/N); frames=[]; total=len(df3)
        for i,frac in enumerate(np.linspace(1/N,1,N)):
            cut=int(frac*total); part=df3.iloc[:cut]
            eye=dict(x=2*np.cos(2*np.pi*frac),y=2*np.sin(2*np.pi*frac),z=1)
            traces=make_traces(part)
            # overlays
            if show_seams:
                for _,g in part.groupby('Layer'): s0,e0=g.iloc[0],g.iloc[-1]; traces.append(go.Scatter3d(x=[s0.X,e0.X],y=[s0.Y,e0.Y],z=[s0.Z,e0.Z],mode='lines',line=dict(color='white',width=2),showlegend=False))
            if show_ext:
                for _,g in part.groupby('Layer'): hi=g.loc[g['Z'].idxmax()]; lo=g.loc[g['Z'].idxmin()]; traces.extend([go.Scatter3d(x=[hi.X],y=[hi.Y],z=[hi.Z],mode='markers',marker=dict(color='yellow',size=4),showlegend=False),go.Scatter3d(x=[lo.X],y=[lo.Y],z=[lo.Z],mode='markers',marker=dict(color='orange',size=4),showlegend=False)])
            if show_ss and not part.empty:
                spt,ept=part.iloc[0],part.iloc[-1]; traces.extend([go.Scatter3d(x=[spt.X],y=[spt.Y],z=[spt.Z],mode='markers',marker=dict(color='green',size=6),showlegend=False),go.Scatter3d(x=[ept.X],y=[ept.Y],z=[ept.Z],mode='markers',marker=dict(color='red',size=6),showlegend=False)])
            frames.append(go.Frame(data=traces,name=f'f{i}',layout=dict(scene_camera=dict(eye=eye))))
        fig=go.Figure(data=make_traces(df3),frames=frames)
        fig.update_layout(updatemenus=[dict(type='buttons',showactive=False,buttons=[dict(label='▶️ Play',method='animate',args=[None,dict(frame=dict(duration=fd,redraw=True),transition=dict(duration=0),fromcurrent=True)])])])
        # download button
        st.download_button('Download Animation (HTML)',fig.to_html(include_plotlyjs='cdn'),file_name='anim.html',mime='text/html')
    else:
        fig=go.Figure(data=make_traces(df3))
        if show_seams:
            for _,g in df3.groupby('Layer'): s0,e0=g.iloc[0],g.iloc[-1]; fig.add_trace(go.Scatter3d(x=[s0.X,e0.X],y=[s0.Y,e0.Y],z=[s0.Z,e0.Z],mode='lines',line=dict(color='white',width=2),showlegend=False))
        if show_ext:
            for _,g in df3.groupby('Layer'): hi=g.loc[g['Z'].idxmax()]; lo=g.loc[g['Z'].idxmin()]; fig.add_trace(go.Scatter3d(x=[hi.X],y=[hi.Y],z=[hi.Z],mode='markers',marker=dict(color='yellow',size=4),showlegend=False)); fig.add_trace(go.Scatter3d(x=[lo.X],y=[lo.Y],z=[lo.Z],mode='markers',marker=dict(color='orange',size=4),showlegend=False))
        if show_ss and not df3.empty:
            spt,ept=df3.iloc[0],df3.iloc[-1]; fig.add_trace(go.Scatter3d(x=[spt.X],y=[spt.Y],z=[spt.Z],mode='markers',marker=dict(color='green',size=6),showlegend=False)); fig.add_trace(go.Scatter3d(x=[ept.X],y=[ept.Y],z=[ept.Z],mode='markers',marker=dict(color='red',size=6),showlegend=False))
    fig.update_layout(scene=dict(xaxis_title='X (mm)',yaxis_title='Y (mm)',zaxis_title='Z (mm)',aspectmode='data'),template='plotly_dark',height=700,margin=dict(l=0,r=0,b=0,t=0))
    st.plotly_chart(fig,use_container_width=False,width=900)

# XYZ Over Time
with st.expander("📈 XYZ Axes Over Time",expanded=True):
    mxyz=st.selectbox("XYZ Plot Mode:",['Raw','Layer Average'],key='xyzm')
    axes=st.multiselect("Select XYZ axes:",['X','Y','Z'],default=['X','Y','Z'],key='xyzs')
    if axes:
        dfx=df_slice.sort_values('Time Step')
        fig=px.line(dfx,x='Time Step',y=axes,template='plotly_dark') if mxyz=='Raw' else px.line(df_slice.groupby('Layer')[axes].mean().reset_index(),x='Layer',y=axes,template='plotly_dark')
        fig.update_layout(height=800)
        st.plotly_chart(fig,use_container_width=False,width=900)

# ABC Over Time
with st.expander("📈 ABC Axes Over Time",expanded=True):
    mabc=st.selectbox("ABC Plot Mode:",['Raw','Layer Average'],key='abcm')
    axes=st.multiselect("Select ABC axes:",['A','B','C'],default=['A','B','C'],key='abcs')
    if axes:
        dfx=df_slice.sort_values('Time Step')
        fig=px.line(dfx,x='Time Step',y=axes,template='plotly_dark') if mabc=='Raw' else px.line(df_slice.groupby('Layer')[axes].mean().reset_index(),x='Layer',y=axes,template='plotly_dark')
        fig.update_layout(height=500)
        st.plotly_chart(fig,use_container_width=False,width=900)

# Data Table & Export
with st.expander('📄 Data Table & Export',expanded=False):
    st.dataframe(df_slice,use_container_width=True)
    st.download_button('Download CSV',df_slice.to_csv(index=False).encode(),'motion_data.csv','text/csv')
