import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="G-code Analyzer Dashboard", layout="wide")
st.title("🧠 G-code / MPF Analyzer Dashboard")

# File uploader
uploaded_file = st.file_uploader("Upload your .gcode or .mpf file", type=["gcode", "mpf", "txt"])

if uploaded_file:
    lines = uploaded_file.read().decode("utf-8").splitlines()

    # Extract XYZABCE and Layer data
    data = {
        "Time Step": [], "X": [], "Y": [], "Z": [], "A": [], "B": [], "C": [], "E": [], "Layer": []
    }
    current_layer = -1
    time_counter = 0

    for line in lines:
        if ";-----------------------LAYER" in line:
            layer_match = re.search(r"LAYER\s+(\d+)", line)
            if layer_match:
                current_layer = int(layer_match.group(1))
        elif "G1" in line and any(axis in line for axis in ["X", "Y", "Z", "A", "B", "C", "E"]):
            x = y = z = a = b = c = e = None
            if (m := re.search(r"X([-+]?[0-9]*\.?[0-9]+)", line)): x = float(m.group(1))
            if (m := re.search(r"Y([-+]?[0-9]*\.?[0-9]+)", line)): y = float(m.group(1))
            if (m := re.search(r"Z([-+]?[0-9]*\.?[0-9]+)", line)): z = float(m.group(1))
            if (m := re.search(r"A([-+]?[0-9]*\.?[0-9]+)", line)): a = float(m.group(1))
            if (m := re.search(r"B([-+]?[0-9]*\.?[0-9]+)", line)): b = float(m.group(1))
            if (m := re.search(r"C([-+]?[0-9]*\.?[0-9]+)", line)): c = float(m.group(1))
            if (m := re.search(r"E([-+]?[0-9]*\.?[0-9]+)", line)): e = float(m.group(1))

            data["Time Step"].append(time_counter)
            data["X"].append(x)
            data["Y"].append(y)
            data["Z"].append(z)
            data["A"].append(a)
            data["B"].append(b)
            data["C"].append(c)
            data["E"].append(e)
            data["Layer"].append(current_layer)
            time_counter += 1

    df = pd.DataFrame(data)
    st.success(f"Parsed {len(df)} motion commands across {df['Layer'].nunique()} layers.")

    all_layers = df["Layer"].dropna().unique().astype(int)

    if len(all_layers) == 0:
        st.warning("No valid layer data found. Make sure your file contains motion data and layer markers.")
    else:
        # Sidebar filters
        st.sidebar.header("Layer Filter")
        selected_layers = st.sidebar.slider("Select layer range", int(all_layers.min()), int(all_layers.max()), (int(all_layers.min()), int(all_layers.max())))

        filtered_df = df[df["Layer"].between(*selected_layers)]

        # Tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Graphs", "📐 Stats", "📄 Data Table", "🧭 XY Toolpath Preview", "🧪 Extrusion"])

        with tab1:
            st.subheader("Axis Movement Over Time")
            for axis in ["X", "Y", "Z", "A", "B", "C"]:
                fig = px.line(filtered_df, x="Time Step", y=axis, title=f"{axis} Axis Over Time", markers=True)
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("Summary Statistics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Time Steps", len(df))
                st.metric("Unique Layers", df["Layer"].nunique())
                st.metric("Z Range", f"{df['Z'].min():.2f} mm – {df['Z'].max():.2f} mm")
            with col2:
                st.metric("X Range", f"{df['X'].min():.2f} mm – {df['X'].max():.2f} mm")
                st.metric("Y Range", f"{df['Y'].min():.2f} mm – {df['Y'].max():.2f} mm")
                st.metric("C Axis Range", f"{df['C'].min():.2f}° – {df['C'].max():.2f}°")

            st.divider()
            st.subheader("Layer Heights with Anomaly Detection")
            z_layers = df.dropna(subset=["Z"])
            z_by_layer = z_layers.groupby("Layer")["Z"].first().sort_index()
            layer_heights = z_by_layer.diff().dropna()

            valid_steps = set(round(0.1 * i, 3) for i in range(0, 41))
            rounded_layer_heights = layer_heights.round(3)
            anomalies = rounded_layer_heights[~rounded_layer_heights.isin(valid_steps)]

            fig_height = px.line(layer_heights, title="Layer Height Over Layers")
            fig_height.add_scatter(x=anomalies.index, y=anomalies.values, mode='markers', name='Anomalies', marker=dict(color='red', size=10))
            st.plotly_chart(fig_height, use_container_width=True)

        with tab3:
            st.subheader("Motion Data Table")
            st.dataframe(filtered_df, use_container_width=True)

            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "motion_data.csv", "text/csv")

        with tab4:
            st.subheader("XY Toolpath Preview by Layer")
            layer_option = st.selectbox("Choose a specific layer to preview: ", sorted(all_layers))
            layer_df = df[df["Layer"] == layer_option].dropna(subset=["X", "Y"])

            if not layer_df.empty:
                fig_xy = px.scatter(layer_df, x="X", y="Y", title=f"XY Toolpath - Layer {layer_option}", labels={"X": "X (mm)", "Y": "Y (mm)"})
                fig_xy.update_traces(mode="lines+markers")
                fig_xy.update_layout(height=500, yaxis_scaleanchor="x", yaxis_autorange="reversed")
                st.plotly_chart(fig_xy, use_container_width=True)
            else:
                st.warning("No valid X/Y data for this layer.")

        with tab5:
            st.subheader("Extrusion Over Time")
            if df["E"].notna().sum() > 0:
                fig_e = px.line(df.dropna(subset=["E"]), x="Time Step", y="E", title="E-axis Extrusion Over Time", markers=True)
                st.plotly_chart(fig_e, use_container_width=True)
                total_e = df["E"].dropna().diff().clip(lower=0).sum()
                st.metric("Estimated Material Extruded", f"{total_e:.2f} units")
            else:
                st.info("No E-axis extrusion data found in the uploaded file.")
