import streamlit as st, plotly.graph_objects as go, numpy as np, time
from threading import Thread, Lock
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

ID = 38
MAX_POINTS = 300

st.set_page_config(layout="wide")
st.title("Minimal OptiTrack Live View")

# INITIALIZE SYSTEM -> only ones
if 'lock' not in st.session_state:
    st.session_state.lock = Lock()
    st.session_state.live_buffer = []

    #Start NatNet
    st.session_state.monitor = NatNetRigidBodyMonitor()
    st.session_state.monitor.start()

    #Polling Thread -> take OptiTrack data
    def fetch_instant_data():
        while True:
            pos = st.session_state.monitor.get_position(ID)
            if pos is not None:
                with st.session_state.lock:
                    st.session_state.live_buffer.append(list(pos))
                    if len(st.session_state.live_buffer) > MAX_POINTS:
                        st.session_state.live_buffer.pop(0)
            time.sleep(0.05)
    Thread(target=fetch_instant_data, daemon=True).start() #initialisate thread for taking data from OptiTrack

plot_spot = st.empty() #for 3D plot

# REFRESH LOOP
while True:
    with st.session_state.lock:
        data = np.array(st.session_state.live_buffer)

    fig = go.Figure() #initialisate figure where to plot OptiTrack data

    if len(data) > 0:
        fig.add_trace(go.Scatter3d(
            x=data[:, 0], y=data[:, 1], z=data[:, 2],
            mode='lines+markers',
            name='Drone',
            marker=dict(size=4, color='red'),
            line=dict(color='red', width=2)
        ))

    fig.update_layout( # Lock the axes to the scale of flying area
        height=700,
        margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            aspectmode='cube',
            xaxis_range=[-2, 2],
            yaxis_range=[-2, 2],
            zaxis_range=[0, 2]
        )
    )

    plot_spot.plotly_chart(fig, width='stretch')
    time.sleep(0.1)