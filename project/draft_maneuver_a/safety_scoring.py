class VirtualCage:
    def __init__(self, x_bounds, y_bounds, z_bounds):
        self.x_min, self.x_max = x_bounds
        self.y_min, self.y_max = y_bounds
        self.z_min, self.z_max = z_bounds

#implement algorithm for scoring accuracy of drawn trajectory

#also to add live dashboard to show in real time ideal VS real data