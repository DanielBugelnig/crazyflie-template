import sys
import time
from pathlib import Path
from threading import Thread, Lock

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Allow crazyflie imports
sys.path.append(str(Path(__file__).resolve().parents[2]))
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

# -----------------------------
# CONFIG
# -----------------------------
ID = 38
MAX_POINTS = 300

st.set_page_config(layout="wide")
st.title("Thread-Safe OptiTrack Live View")


# -----------------------------
# GLOBAL BUFFER AND LOCK
# -----------------------------
buffer_lock = Lock()
live_buffer = []

# -----------------------------
# MONITOR INITIALIZATION
# -----------------------------
if "monitor" not in st.session_state:
    st.session_state.monitor = NatNetRigidBodyMonitor()
    st.session_state.monitor.start()

monitor = st.session_state.monitor

# -----------------------------
# BACKGROUND THREAD
# -----------------------------
if "thread_started" not in st.session_state:
    def fetch_instant_data(monitor):
        while True:
            pos = monitor.get_position(ID)
            # print(pos)
            if pos is not None:
                with buffer_lock:
                    live_buffer.append(list(pos))
                    if len(live_buffer) > MAX_POINTS:
                        live_buffer.pop(0)
            time.sleep(0.05)

    thread = Thread(target=fetch_instant_data, args=(monitor,), daemon=True)
    thread.start()
    st.session_state.thread_started = True

# -----------------------------
# PLOT DATA
# -----------------------------

# Refresh UI every 100 ms
st_autorefresh(interval=100, key="optitrack_refresh")

plot_spot = st.empty()

# always get latest buffer
with buffer_lock:
    data = np.array(live_buffer.copy())

fig = go.Figure()

if data.shape[0] > 0:
    fig.add_trace(
        go.Scatter3d(
            x=data[:,0],
            y=data[:,1],
            z=data[:,2],
            mode="lines+markers",
            name="Drone",
            marker=dict(size=4, color="red"),
            line=dict(color="red", width=2),
        )
    )

fig.update_layout(
    height=700,
    margin=dict(l=0,r=0,b=0,t=0),
    scene=dict(
        aspectmode="cube",
        xaxis_range=[-2,2],
        yaxis_range=[-2,2],
        zaxis_range=[0,2],
        xaxis_title="X",
        yaxis_title="Y",
        zaxis_title="Z"
    )
)

plot_spot.plotly_chart(fig, use_container_width=True)
# plot_spot = st.empty()

# with buffer_lock:
#     data = np.array(live_buffer.copy())

# fig = go.Figure()

# if len(data) > 0:
#     fig.add_trace(
#         go.Scatter3d(
#             x=data[:,0],
#             y=data[:,1],
#             z=data[:,2],
#             mode="lines+markers",
#             name="Drone",
#             marker=dict(size=4, color="red"),
#             line=dict(color="red", width=2),
#         )
#     )

# fig.update_layout(
#     height=700,
#     margin=dict(l=0,r=0,b=0,t=0),
#     scene=dict(
#         aspectmode="cube",
#         xaxis_range=[-2,2],
#         yaxis_range=[-2,2],
#         zaxis_range=[0,2],
#         xaxis_title="X",
#         yaxis_title="Y",
#         zaxis_title="Z"
#     )
# )

# plot_spot.plotly_chart(fig, width="stretch", key="optitrack_chart")