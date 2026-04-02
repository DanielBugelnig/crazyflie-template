import streamlit as st, plotly.graph_objects as go, numpy as np, pandas as pd
from pathlib import Path
from trajectory_math import load_waypoints, add_yaw

st.set_page_config(layout="wide")
st.title("Interactive Dashboard")

# Initialize session state
if 'real_points' not in st.session_state:
    st.session_state.real_points = []

# Load Ideal Trajectory
@st.cache_data
def get_traj_data(path):
    base_path = Path(__file__).resolve().parents[0]
    filepath = base_path / path
    data = load_waypoints(filepath)
    if data.shape[1] == 3: data = np.column_stack((data, np.zeros(len(data)))) #add fourth column for yaw
    return data

ideal = get_traj_data('ideal_trajectories/circle.csv')


# if st.session_state.real_points is None:
#     try:
#         initial_real = get_traj_data('trajectories/test_trajectory_processed.csv')
#
#         if initial_real.shape[1] < 4:
#             initial_real = add_yaw(initial_real)
#         st.session_state.real_points = initial_real.tolist()
#     except:
#         st.session_state.real_points = []


# --- Sidebar Inputs ---
st.sidebar.header("Manual Input")
user_input = st.sidebar.text_input("Enter x y z (e.g., 1 2 4)", key="coord_input")

if st.sidebar.button("Add Point"):
    try:
        coords = [float(val) for val in user_input.split()]
        if len(coords) == 3:

            new_point = coords + [0.0]
            st.session_state.real_points.append(new_point)

            temp_arr = np.array(st.session_state.real_points)

            updated_arr = add_yaw(temp_arr[:, :3])  # Only pass X, Y, Z to add_yaw

            st.session_state.real_points = updated_arr.tolist()
            st.sidebar.success(f"Added: {coords}")
        else:
            st.sidebar.error("Need exactly 3 numbers!")
    except ValueError:
        st.sidebar.error("Invalid numbers!")

# --- Plotting ---
fig = go.Figure()

# Plot Ideal (Blue Line)
fig.add_trace(go.Scatter3d(
    x=ideal[:, 0], y=ideal[:, 1], z=ideal[:, 2],
    mode='lines', name='Ideal Path', line=dict(color='royalblue', width=2)
))

# Plot Real Data
if len(st.session_state.real_points) > 0:
    real_data = np.array(st.session_state.real_points)

    # Gradient (Progress)
    # fig.add_trace(go.Scatter3d(
    #     x=real_data[:, 0], y=real_data[:, 1], z=real_data[:, 2],
    #     mode='lines+markers',
    #     name='Real Flight',
    #     marker=dict(
    #         size=4,
    #         color=np.arange(len(real_data)),
    #         colorscale='Viridis',
    #         showscale=True,
    #         colorbar=dict(title="Time Steps", x=-0.1)
    #     ),
    #     line=dict(color='crimson', width=3)
    # ))


    step = 2
    yaws_rad = np.radians(real_data[::step, 3])

    fig.add_trace(go.Cone(
        x=real_data[::step, 0], y=real_data[::step, 1], z=real_data[::step, 2],
        u=np.cos(yaws_rad), v=np.sin(yaws_rad), w=np.zeros_like(yaws_rad),
        sizemode="absolute", sizeref=0.15,
        colorscale=[[0, 'orange'], [1, 'orange']],
        showscale=False,
        name='Drone Orientation'
    ))

fig.update_layout(
    height=700,
    margin=dict(l=0, r=0, b=0, t=40),
    scene=dict(
        aspectmode='data',
        xaxis_title='X [m]',
        yaxis_title='Y [m]',
        zaxis_title='Z [m]'
    )
)

st.plotly_chart(fig, width='stretch')