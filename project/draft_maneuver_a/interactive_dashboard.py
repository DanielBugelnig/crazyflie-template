import streamlit as st, plotly.graph_objects as go, numpy as np, time
from threading import Thread, Lock
from pathlib import Path

from trajectory_math import load_waypoints, add_yaw
from main_tracker import get_average_position
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

#CONFIGURATION
ID = 38
UPDATE_RATE = 10
MOCAP_TX_RATE_HZ = 100

st.set_page_config(layout="wide", page_title="Drone Live Monitor")

#SHARED STATE
if 'lock' not in st.session_state:
    st.session_state.lock = Lock()
if 'live_buffer' not in st.session_state:
    st.session_state.live_buffer = []
if 'recording' not in st.session_state:
    st.session_state.recording = False


def run_optitrack_thread(monitor, rb_id):
    while True:
        avg_pos = get_average_position(monitor, rb_id)

        if avg_pos is not None:
            with st.session_state.lock:
                st.session_state.live_buffer.append(list(avg_pos))
                if len(st.session_state.live_buffer) > 500: st.session_state.live_buffer.pop(0)


#Start NatNet
if 'monitor' not in st.session_state:
    st.session_state.monitor = NatNetRigidBodyMonitor()
    st.session_state.monitor.start()

    tracker_thread = Thread(
        target=run_optitrack_thread,
        args=(st.session_state.monitor, ID),
        daemon=True
    )
    tracker_thread.start()


#LOAD IDEAL PATH
@st.cache_data
def get_ideal_path():
    # Adjust this path to your actual circle.csv location
    path = Path(__file__).resolve().parents[0] / 'ideal_trajectories/circle.csv'
    return load_waypoints(path)

ideal_data = get_ideal_path()

#UI LAYOUT
st.title("OptiTrack Live Trajectory Dashboard")

col1, col2 = st.columns([1, 4]) #two columns where first is 1x, second is 4x
with col1:
    st.metric("Rigid Body ID", ID)
    if st.button("🗑️ Clear Live View"):
        with st.session_state.lock:
            st.session_state.live_buffer = []

plot_spot = st.empty() #3D plot

#UPDATING
while True:
    with st.session_state.lock:
        current_points = np.array(st.session_state.live_buffer)

    fig = go.Figure()

    #IDEAL PATH (Blue)
    fig.add_trace(go.Scatter3d(
        x=ideal_data[:, 0], y=ideal_data[:, 1], z=ideal_data[:, 2],
        mode='lines', name='Ideal (Reference)',
        line=dict(color='rgba(0, 0, 255, 0.3)', width=4)
    ))

    #REAL DATA (Red)
    if len(current_points) > 0:
        fig.add_trace(go.Scatter3d(
            x=current_points[:, 0], y=current_points[:, 1], z=current_points[:, 2],
            mode='lines+markers', name='Actual (OptiTrack)',
            marker=dict(size=3, color='crimson'),
            line=dict(color='crimson', width=3)
        ))

    #STYLING
    fig.update_layout(
        height=800,
        scene=dict(
            aspectmode='data',
            xaxis_title="X [m]", yaxis_title="Y [m]", zaxis_title="Z [m]",
            xaxis=dict(range=[-2, 2]), yaxis=dict(range=[-2, 2]), zaxis=dict(range=[0, 2])
        ),
        margin=dict(l=0, r=0, b=0, t=0)
    )

    plot_spot.plotly_chart(fig, width='stretch')
    time.sleep(0.2)