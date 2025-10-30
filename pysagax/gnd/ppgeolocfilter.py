"""Kálmán filter for geolocation data"""

import numpy as np
from scipy.linalg import block_diag


import numpy as np
import datetime

from collections import deque
# from time import time 


class BaseFilter:
    """Defines how a geolocation filter should look like"""
    def __init__(self, initial_state, initial_uncertainty = None, process_noise = None, measurement_noise = None, initial_timestamp = None, window_span = None):
        pass

    def predict(self, dt):
        pass # not needed

    def update(self, measurement, timestamp):
        pass

    def get_state(self):
        pass

    def get_prediction(self):
        pass

class RecursiveAverageFilter(BaseFilter):
    def __init__(self, initial_state, window_span, *args, **kwargs ):
        """
        Initializes the a moving window filter
        
        initial_state: Initial state [x, y, vx, vy]
        rest of the parameters are only there for compatibility with other filters
        """
        lat, lon, _, _ = initial_state


        self.filtered_lat = lat
        self.filtered_lon = lon
        self.last_timestamp = None

        self.time_constant = window_span
        self.vlat = 0.0
        self.vlon = 0.0


    def predict(self, dt):
        pass # not needed

    def update(self, measurement, timestamp):
        """
        Updates the state with a new measurement.
        
        :param measurement: GPS measurement [x, y]
        :param timestamp: Timestamp of the measurement
        """
        lat, lon = measurement

        if self.last_timestamp is None:
            self.last_timestamp = timestamp
            return

        dt = timestamp - self.last_timestamp
        self.last_timestamp = timestamp

        if dt <= 0:
            return  # avoid divide by zero or going backwards in time

        alpha = dt / (self.time_constant + dt)

        # Update filtered values
        prev_lat = self.filtered_lat
        prev_lon = self.filtered_lon

        self.filtered_lat += alpha * (lat - self.filtered_lat)
        self.filtered_lon += alpha * (lon - self.filtered_lon)

        # Rate of change (smoothed velocity)
        self.vlat = (self.filtered_lat - prev_lat) / dt
        self.vlon = (self.filtered_lon - prev_lon) / dt

    def get_state(self):
        """
        Returns the current estimated state.
        """
        return self.filtered_lat, self.filtered_lon, self.vlat, self.vlon
    
    def get_prediction(self):
        """
        Returns the predicted state.
        """
        return self.state_pred.copy()


class MovingWindowAverage(BaseFilter):
    def __init__(self, initial_state, initial_timestamp, window_span, *args, **kwargs):
        """
        Initializes the a moving window filter
        
        initial_state: Initial state [x, y, vx, vy]

        """
        lat, lon, _, _ = initial_state
        self.window_span = window_span
        self.data = deque() # stores tuples of (timestamp, lat, lon)

        # if isinstance()

        self.data.append((initial_timestamp.timestamp(), lat, lon))
        self.last_timestamp = None

    def predict(self, dt):
        pass # not needed

    def update(self, measurement, timestamp):
        """
        Updates the state with a new measurement.
        
        :param measurement: GPS measurement [x, y]
        :param timestamp: Timestamp of the measurement
        """
        lat, lon = measurement

        # Add new data point
        self.data.append((timestamp.timestamp(), lat, lon))

        # Remove old data points outside the window
        while self.data and (timestamp.timestamp() - self.data[0][0] > self.window_span):
            self.data.popleft()


        self.last_timestamp = timestamp

    def get_state(self):
        """
        Returns the current estimated state.
        """
        if not len(self.data):
            # data is empty
            _, lat, lon = self.data[-1]
            return float("NaN"), float("NaN"), float("NaN"), float("NaN")

        # Compute average lat and lon
        total_lat = sum(point[1] for point in self.data)
        total_lon = sum(point[2] for point in self.data)
        avg_lat = total_lat / len(self.data)
        avg_lon = total_lon / len(self.data)

        # speed using first and last points
        t0, lat0, lon0 = self.data[0]
        t1, lat1, lon1 = self.data[-1]
        dt = t1 - t0

        if dt:
            dx_dt = (lat1 - lat0) / dt
            dy_dt = (lon1 - lon0) / dt
        else: # dont divide by zero
            dx_dt, dy_dt = 0, 0

        return avg_lat, avg_lon, dx_dt, dy_dt
    
    def get_prediction(self):
        """
        Returns the predicted state.
        """
        return self.state_pred.copy()

class KalmanFilter1(BaseFilter):
    def __init__(self, initial_state, initial_uncertainty, process_noise, measurement_noise, *args, **kwargs):
        """
        Initializes the Kalman Filter for GPS tracking.
        
        :param initial_state: Initial state [x, y, vx, vy]
        :param initial_uncertainty: Initial covariance matrix (4x4)
        :param process_noise: Process noise covariance matrix (4x4)
        :param measurement_noise: Measurement noise covariance matrix (2x2)
        """
        self.state = np.zeros(4)
        self.state_pred = np.array(initial_state, dtype=float)
        self.P = np.array(initial_uncertainty, dtype=float)
        self.Q = np.array(process_noise, dtype=float)
        self.R = np.array(measurement_noise, dtype=float)
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])  # Measurement matrix
        self.I = np.eye(4)  # Identity matrix
        self.last_timestamp = None

    def predict(self, dt):
        """
        Predicts the next state based on the time difference dt.
        
        :param dt: Time difference since the last update in seconds
        """
        if isinstance(dt, datetime.timedelta):
            dt = dt.total_seconds()
        if dt<=0:
            print("DT is ", dt)
        F = np.array([[1, 0, dt, 0],
                      [0, 1, 0, dt],
                      [0, 0, 1, 0],
                      [0, 0, 0, 1]])  # State transition model

        self.state_pred = F @ self.state  # Predict state
        self.P = F @ self.P @ F.T + self.Q  # Predict uncertainty

    def update(self, measurement, timestamp):
        """
        Updates the state with a new measurement.
        
        :param measurement: GPS measurement [x, y]
        :param timestamp: Timestamp of the measurement
        """
        measurement = np.array(measurement, dtype=float)
        
        if self.last_timestamp is not None:
            dt = timestamp - self.last_timestamp
            self.predict(dt)
        
        self.last_timestamp = timestamp
        
        # Kalman Gain calculation
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Update step
        y = measurement - self.H @ self.state_pred
        self.state = self.state_pred + K @ y
        self.P = (self.I - K @ self.H) @ self.P

    def get_state(self):
        """
        Returns the current estimated state.
        """
        return self.state.copy()
    
    def get_prediction(self):
        """
        Returns the predicted state.
        """
        return self.state_pred.copy()


class KalmanFilter1B(BaseFilter):
    def __init__(self, initial_state, initial_uncertainty, process_noise, measurement_noise, *args, **kwargs):
        """
        Initializes the Kalman Filter for GPS tracking.
        
        :param initial_state: Initial state [x, y, vx, vy]
        :param initial_uncertainty: Initial covariance matrix (4x4)
        :param process_noise: Process noise covariance matrix (4x4)
        :param measurement_noise: Measurement noise covariance matrix (2x2)
        """
        self.state = np.zeros(6)
        self.state_pred = np.array(initial_state, dtype=float)
        self.P = np.array(initial_uncertainty, dtype=float)
        self.Q = np.array(process_noise, dtype=float)
        self.R = np.array(measurement_noise, dtype=float)
        self.H = np.array([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]])  # Measurement matrix
        self.I = np.eye(6)  # Identity matrix
        self.last_timestamp = None

    def predict(self, dt):
        """
        Predicts the next state based on the time difference dt.
        
        :param dt: Time difference since the last update in seconds
        """
        if isinstance(dt, datetime.timedelta):
            dt = dt.total_seconds()
        F = np.array([[1, 0, dt, 0, dt**2/2, 0],
                      [0, 1, 0, dt, 0, dt**2/2],
                      [0, 0, 1, 0, dt, 0],
                      [0, 0, 0, 1, 0, dt],
                      [0, 0, 0, 0, 1, 0],
                      [0, 0, 0, 0, 0, 1]])  # State transition model

        self.state_pred = F @ self.state  # Predict state
        self.P = F @ self.P @ F.T + self.Q  # Predict uncertainty

    def update(self, measurement, timestamp):
        """
        Updates the state with a new measurement.
        
        :param measurement: GPS measurement [x, y]
        :param timestamp: Timestamp of the measurement
        """
        measurement = np.array(measurement, dtype=float)
        
        if self.last_timestamp is not None:
            dt = timestamp - self.last_timestamp
            self.predict(dt)
        
        self.last_timestamp = timestamp
        
        # Kalman Gain calculation
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # Update step
        y = measurement - self.H @ self.state_pred
        self.state = self.state_pred + K @ y
        self.P = (self.I - K @ self.H) @ self.P

    def get_state(self):
        """
        Returns the current estimated state.
        """
        return self.state.copy()
    
    def get_prediction(self):
        """
        Returns the predicted state.
        """
        return self.state_pred.copy()




class KalmanFilter2(BaseFilter):
    """
    Kalman filter implementation for tracking GPS coordinates with irregular time intervals.
    
    State vector: [x, y, vx, vy]
    - x, y: Position coordinates
    - vx, vy: Velocity in x and y directions
    
    This implementation handles unevenly timed measurements by adjusting the
    state transition matrix based on the time delta between measurements.
    """
    
    def __init__(self, initial_state=None, initial_covariance=None, process_noise=None, measurement_noise=None, *args, **kwargs):
        """
        Initialize the Kalman Filter.
        
        Parameters:
        -----------
        initial_state : array-like, shape (4,)
            Initial state vector [x, y, vx, vy]
        initial_covariance : array-like, shape (4, 4)
            Initial state covariance matrix
        process_noise : array-like, shape (4, 4) or float
            Process noise covariance matrix or scalar for diagonal
        measurement_noise : array-like, shape (2, 2) or float
            Measurement noise covariance matrix or scalar for diagonal
        """
        # State vector [x, y, vx, vy]
        self.state = np.zeros(4) if initial_state is None else np.array(initial_state)
        
        # State covariance matrix
        self.covariance = np.eye(4) if initial_covariance is None else np.array(initial_covariance)
        
        # Process noise (uncertainty in the model)
        if process_noise is None:
            self.process_noise = np.diag([0.1, 0.1, 0.01, 0.01])
        elif isinstance(process_noise, (int, float)):
            self.process_noise = np.eye(4) * process_noise
        else:
            self.process_noise = np.array(process_noise)
            
        # Measurement noise (uncertainty in the measurements)
        if measurement_noise is None:
            self.measurement_noise = np.diag([10.0, 10.0])  # GPS typical noise in meters
        elif isinstance(measurement_noise, (int, float)):
            self.measurement_noise = np.eye(2) * measurement_noise
        else:
            self.measurement_noise = np.array(measurement_noise)
            
        # Measurement matrix (maps state to measurement space)
        self.H = np.array([[1, 0, 0, 0],   # x position
                           [0, 1, 0, 0]])  # y position
        
        # Time of last update
        self.last_timestamp = None

        self.last_prediction = self.state
    
    def _build_state_transition(self, dt):
        """
        Build state transition matrix based on time delta.
        
        Parameters:
        -----------
        dt : float
            Time delta since last measurement in seconds
        
        Returns:
        --------
        F : numpy.ndarray
            State transition matrix
        """
        # State transition matrix for constant velocity model
        # [1, 0, dt, 0]
        # [0, 1, 0, dt]
        # [0, 0, 1, 0]
        # [0, 0, 0, 1]
        F = np.eye(4)
        F[0, 2] = dt
        F[1, 3] = dt
        return F
    
    def _build_process_noise(self, dt):
        """
        Build process noise covariance matrix accounting for time delta.
        
        Parameters:
        -----------
        dt : float
            Time delta since last measurement in seconds
        
        Returns:
        --------
        Q : numpy.ndarray
            Time-adjusted process noise covariance matrix
        """
        # Scale process noise based on time delta
        # For longer time intervals, we expect more uncertainty
        # q_pos = self.process_noise[0, 0] * dt**3 / 3
        # q_pos_vel = self.process_noise[0, 0] * dt**2 / 2
        # q_vel = self.process_noise[2, 2] * dt
        
        # Q_x = np.array([[q_pos, q_pos_vel],
        #                 [q_pos_vel, q_vel]])
        
        # Q_y = np.array([[q_pos, q_pos_vel],
        #                 [q_pos_vel, q_vel]])
        
        # return block_diag(Q_x, Q_y)
        return self.process_noise
    
    def predict(self, timestamp):
        """
        Predict the state forward to the given timestamp.
        
        Parameters:
        -----------
        timestamp : float
            Current timestamp (seconds)
        
        Returns:
        --------
        state : numpy.ndarray
            Predicted state vector
        covariance : numpy.ndarray
            Predicted state covariance
        """
        if self.last_timestamp is None:
            self.last_timestamp = timestamp
            return self.state, self.covariance
        
        # Calculate time delta in seconds
        dt = timestamp - self.last_timestamp
        if isinstance(dt, datetime.timedelta):
            dt = dt.total_seconds()
        
        if dt <= 0:
            return self.state, self.covariance
        
        # Build state transition matrix
        F = self._build_state_transition(dt)
        
        # Predict state
        self.state = F @ self.state
        
        # Predict covariance
        Q = self._build_process_noise(dt)
        self.covariance = F @ self.covariance @ F.T + Q
        
        # Update timestamp
        self.last_timestamp = timestamp
        
        self.last_prediction = self.state

        return self.state, self.covariance
    # I have a simple app that loads raw datapoints, filters them using hard coded parameters, and then plots the results using matplotlib. How can I improve my program so that the parameters are adjustable using a graphical user interface? The parameters in question: P (4*4 matrix), Q (4*4 matrix) and R (2*2 matrix). Their values should be adjustable on a logarithmic scale.
    # How do I make an application that loads raw datapoints, filters them with certain parameters and the plots them using matplotlib. The application should also have graphical
    
    def compute_estimate(self, measurement):
        """
        Update the state with a new measurement.
        
        Parameters:
        -----------
        measurement : array-like, shape (2,)
            Measurement vector [x, y]
        
        Returns:
        --------
        state : numpy.ndarray
            Updated state vector
        covariance : numpy.ndarray
            Updated state covariance
        """
        measurement = np.array(measurement)
        
        # Calculate Kalman gain
        S = self.H @ self.covariance @ self.H.T + self.measurement_noise
        K = self.covariance @ self.H.T @ np.linalg.inv(S)
        
        # Update state
        y = measurement - self.H @ self.state  # Measurement residual
        self.state = self.state + K @ y
        
        # Update covariance using Joseph form for stability
        I = np.eye(self.state.shape[0])
        self.covariance = (I - K @ self.H) @ self.covariance @ (I - K @ self.H).T + K @ self.measurement_noise @ K.T
        
        return self.state, self.covariance
    
    def update(self, measurement, timestamp):
        """
        Process a new GPS point.
        
        Parameters:
        -----------
        x : float
            x-coordinate (e.g., longitude converted to meters)
        y : float
            y-coordinate (e.g., latitude converted to meters)
        timestamp : float
            Timestamp of the measurement
            
        Returns:
        --------
        filtered_position : tuple
            Filtered (x, y) position
        velocity : tuple
            Estimated (vx, vy) velocity
        """
        # Predict state to current timestamp
        self.predict(timestamp)
        
        # Update with new measurement
        self.compute_estimate(measurement)
        
        # Return filtered position and velocity estimate
        return (self.state[0], self.state[1]), (self.state[2], self.state[3])
    
    def get_position(self):
        """Get the current estimated position."""
        return self.state[0], self.state[1]
    
    def get_velocity(self):
        """Get the current estimated velocity."""
        return self.state[2], self.state[3]
    
    def get_state(self):
        """Get the complete state vector."""
        return self.state.copy()
    
    def get_covariance(self):
        """Get the current state covariance matrix."""
        return self.covariance.copy()

    def get_prediction(self):
        return self.last_prediction

class KalmanFilter2B(BaseFilter):
    """
    Kalman filter implementation for tracking GPS coordinates with irregular time intervals.
    
    State vector: [x, y, vx, vy, ax, ay]
    - x, y: Position coordinates
    - vx, vy: Velocity in x and y directions
    - ax, ay: Acceleration in x and y directions
    
    This implementation handles unevenly timed measurements by adjusting the
    state transition matrix based on the time delta between measurements.
    """
    
    def __init__(self, initial_state=None, initial_covariance=None, process_noise=None, measurement_noise=None, *args, **kwargs):
        """
        Initialize the Kalman Filter.
        
        Parameters:
        -----------
        initial_state : array-like, shape (6,)
            Initial state vector [x, y, vx, vy, ax, ay]
        initial_covariance : array-like, shape (6, 6)
            Initial state covariance matrix
        process_noise : array-like, shape (6, 6) or float
            Process noise covariance matrix or scalar for diagonal
        measurement_noise : array-like, shape (2, 2) or float
            Measurement noise covariance matrix or scalar for diagonal
        """
        # State vector [x, y, vx, vy, ax, ay]
        self.state = np.zeros(6) if initial_state is None else np.array(initial_state)
        
        # State covariance matrix
        self.covariance = np.eye(6) if initial_covariance is None else np.array(initial_covariance)
        
        # Process noise (uncertainty in the model)
        if process_noise is None:
            # Default process noise with higher uncertainty for acceleration
            self.process_noise = np.diag([0.1, 0.1, 0.01, 0.01, 0.001, 0.001])
        elif isinstance(process_noise, (int, float)):
            self.process_noise = np.eye(6) * process_noise
        else:
            self.process_noise = np.array(process_noise)
            
        # Measurement noise (uncertainty in the measurements)
        if measurement_noise is None:
            self.measurement_noise = np.diag([10.0, 10.0])  # GPS typical noise in meters
        elif isinstance(measurement_noise, (int, float)):
            self.measurement_noise = np.eye(2) * measurement_noise
        else:
            self.measurement_noise = np.array(measurement_noise)
            
        # Measurement matrix (maps state to measurement space)
        self.H = np.array([[1, 0, 0, 0, 0, 0],   # x position
                           [0, 1, 0, 0, 0, 0]])  # y position
        
        # Time of last update
        self.last_timestamp = None

        self.last_prediction = self.state
    
    def _build_state_transition(self, dt):
        """
        Build state transition matrix based on time delta.
        
        Parameters:
        -----------
        dt : float
            Time delta since last measurement in seconds
        
        Returns:
        --------
        F : numpy.ndarray
            State transition matrix
        """
        # State transition matrix for constant acceleration model
        # [1, 0, dt, 0, 0.5*dt^2, 0]
        # [0, 1, 0, dt, 0, 0.5*dt^2]
        # [0, 0, 1, 0, dt, 0]
        # [0, 0, 0, 1, 0, dt]
        # [0, 0, 0, 0, 1, 0]
        # [0, 0, 0, 0, 0, 1]
        F = np.eye(6)
        
        # Position update includes velocity and acceleration components
        F[0, 2] = dt          # x += vx*dt
        F[0, 4] = 0.5*dt**2   # x += 0.5*ax*dt^2
        F[1, 3] = dt          # y += vy*dt
        F[1, 5] = 0.5*dt**2   # y += 0.5*ay*dt^2
        
        # Velocity update includes acceleration component
        F[2, 4] = dt          # vx += ax*dt
        F[3, 5] = dt          # vy += ay*dt
        
        return F
    
    def _build_process_noise(self, dt):
        """
        Build process noise covariance matrix accounting for time delta.
        
        Parameters:
        -----------
        dt : float
            Time delta since last measurement in seconds
        
        Returns:
        --------
        Q : numpy.ndarray
            Time-adjusted process noise covariance matrix
        """
        # For constant acceleration model, process noise matrix is more complex
        # We need to account for correlations between position, velocity, and acceleration
        
        # Using discretized continuous white noise acceleration model
        dt2 = dt**2
        dt3 = dt**3
        dt4 = dt**4
        
        # Process noise for x-axis
        q_acc_x = self.process_noise[4, 4]  # Variance in x acceleration
        Qx = np.array([
            [dt4/4, dt3/2, dt2/2],
            [dt3/2, dt2, dt],
            [dt2/2, dt, 1]
        ]) * q_acc_x
        
        # Process noise for y-axis
        q_acc_y = self.process_noise[5, 5]  # Variance in y acceleration
        Qy = np.array([
            [dt4/4, dt3/2, dt2/2],
            [dt3/2, dt2, dt],
            [dt2/2, dt, 1]
        ]) * q_acc_y
        
        # Combine into full process noise matrix
        # return block_diag(Qx, Qy)
        return self.process_noise
    
    def predict(self, timestamp):
        """
        Predict the state forward to the given timestamp.
        
        Parameters:
        -----------
        timestamp : float
            Current timestamp (seconds)
        
        Returns:
        --------
        state : numpy.ndarray
            Predicted state vector
        covariance : numpy.ndarray
            Predicted state covariance
        """
        if self.last_timestamp is None:
            self.last_timestamp = timestamp
            return self.state, self.covariance
        
        # Calculate time delta in seconds
        dt = timestamp - self.last_timestamp
        if isinstance(dt, datetime.timedelta):
            dt = dt.total_seconds()
        
        if dt <= 0:
            return self.state, self.covariance
        
        # Build state transition matrix
        F = self._build_state_transition(dt)
        
        # Predict state
        self.state = F @ self.state
        
        # Predict covariance
        Q = self._build_process_noise(dt)
        self.covariance = F @ self.covariance @ F.T + Q
        
        # Update timestamp
        self.last_timestamp = timestamp

        self.last_prediction = self.state
        
        return self.state, self.covariance
    
    def compute_estimate(self, measurement):
        """
        Update the state with a new measurement.
        
        Parameters:
        -----------
        measurement : array-like, shape (2,)
            Measurement vector [x, y]
        
        Returns:
        --------
        state : numpy.ndarray
            Updated state vector
        covariance : numpy.ndarray
            Updated state covariance
        """
        measurement = np.array(measurement)
        
        # Calculate Kalman gain
        S = self.H @ self.covariance @ self.H.T + self.measurement_noise
        K = self.covariance @ self.H.T @ np.linalg.inv(S)
        
        # Update state
        y = measurement - self.H @ self.state  # Measurement residual
        self.state = self.state + K @ y
        
        # Update covariance using Joseph form for stability
        I = np.eye(self.state.shape[0])
        self.covariance = (I - K @ self.H) @ self.covariance @ (I - K @ self.H).T + K @ self.measurement_noise @ K.T
        
        return self.state, self.covariance
    
    def update(self,  measurement, timestamp):
        """
        Process a new GPS point.
        
        Parameters:
        -----------
        x : float
            x-coordinate (e.g., longitude converted to meters)
        y : float
            y-coordinate (e.g., latitude converted to meters)
        timestamp : float
            Timestamp of the measurement
            
        Returns:
        --------
        filtered_position : tuple
            Filtered (x, y) position
        velocity : tuple
            Estimated (vx, vy) velocity
        acceleration : tuple
            Estimated (ax, ay) acceleration
        """
        # Predict state to current timestamp
        self.predict(timestamp)
        
        # Update with new measurement
        self.compute_estimate(measurement)
        
        # Return filtered position, velocity and acceleration estimate
        return (self.state[0], self.state[1]), (self.state[2], self.state[3]), (self.state[4], self.state[5])
    
    def get_position(self):
        """Get the current estimated position."""
        return self.state[0], self.state[1]
    
    def get_velocity(self):
        """Get the current estimated velocity."""
        return self.state[2], self.state[3]
    
    def get_acceleration(self):
        """Get the current estimated acceleration."""
        return self.state[4], self.state[5]
    
    def get_state(self):
        """Get the complete state vector."""
        return self.state.copy()
    
    def get_covariance(self):
        """Get the current state covariance matrix."""
        return self.covariance.copy()
    
    def get_prediction(self):
        return self.last_prediction

class KalmanFilter3(BaseFilter):
    def __init__(self, initial_state, initial_covariance, process_noise, measurement_noise, *args, **kwargs):
        """
        Initialize the Kalman Filter for GPS data.

        Parameters:
        - initial_state: Initial state vector [x, y, vx, vy]
        - initial_covariance: Initial covariance matrix (4x4)
        - process_noise: Process noise covariance matrix (4x4)
        - measurement_noise: Measurement noise covariance matrix (2x2)
        """
        self.state = initial_state
        self.covariance = initial_covariance
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise

        self.last_timestamp = None
        self.last_prediction = self.state

    def predict(self, dt):
        """
        Predict the next state based on the current state and time interval dt.

        Parameters:
        - dt: Time interval between the current and next state
        """

        if isinstance(dt, datetime.timedelta):
            dt = dt.total_seconds()
        # State transition matrix
        F = np.array([[1, 0, dt, 0],
                      [0, 1, 0, dt],
                      [0, 0, 1, 0],
                      [0, 0, 0, 1]])

        # Predict the next state
        self.state = F @ self.state

        # Predict the next covariance
        self.covariance = F @ self.covariance @ F.T + self.process_noise

        self.last_prediction = self.state

    def estimate(self, measurement):
        """
        Update the state based on the GPS measurement.

        Parameters:
        - measurement: GPS measurement vector [x, y]
        """
        # Measurement matrix
        H = np.array([[1, 0, 0, 0],
                      [0, 1, 0, 0]])

        # Measurement residual
        y = measurement - H @ self.state

        # Residual covariance
        S = H @ self.covariance @ H.T + self.measurement_noise

        # Kalman gain
        K = self.covariance @ H.T @ np.linalg.inv(S)

        # Update the state
        self.state = self.state + K @ y

        # Update the covariance
        I = np.eye(K.shape[0])
        self.covariance = (I - K @ H) @ self.covariance
    
    def update(self, measurement, timestamp):

        # Predict state to current timestamp
        if self.last_timestamp is not None:
            dt = timestamp - self.last_timestamp
            self.predict(dt)
        
        self.last_timestamp = timestamp
        
        # Update with new measurement
        self.estimate(measurement)
        
        # Return filtered position and velocity estimate
        return (self.state[0], self.state[1]), (self.state[2], self.state[3])

    def get_state(self):
        """
        Get the current state estimate.

        Returns:
        - state: Current state vector [x, y, vx, vy]
        """
        return self.state

    def get_prediction(self):
        return self.last_prediction