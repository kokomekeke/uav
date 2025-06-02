from __future__ import annotations
import logging
from queue import Queue
import time

from typing import Optional

import geographiclib.geodesic

from pysagax.common.loop import Loop


from pysagax.gnd.database import ComIntDatabase, ComIntDetectionEntity, UAVEntity, ComIntEventEntity, ComIntGeoLocEntity


from typing import Any, Callable, Optional

import numpy as np
from pysagax.util.mat import normalize_angle
import pysagax.message.data_pb2 as proto_data
from pysagax.util.queue_put import queue_put

class PPGeoLoc(Loop):
    """Background process for calculation the geolocation data for the ComInt events"""

    def __init__(
        self,
        db: ComIntDatabase,
        *args,
        **kwargs,
    ) -> None:
        # Loop.__init__(self, *args, **kwargs)
        super().__init__(*args, **kwargs)

        self._db: ComIntDatabase = db
        self._app: Optional[Any] = None

        self._apm_queue: Optional[Queue]= None

    def __call__(
        self,
        apm_queue,
        *args,
        **kwargs,
    ) -> None:
        self._app = self._db.get_app_instance()
        self._apm_queue = apm_queue
        return super()._call(*args, **kwargs)

    def _pair_detections(self, threshold_seconds = 2): #10000):
        """
        return a list of pairs of detections. 
        Geolocation will run on paired detections, so detections should be paired if they are of the same transmitter (frequency/roi_id), made by different UAVs, but are close in time.
        """
        #TODO
        from sqlalchemy.orm import aliased
        from sqlalchemy import and_, func
        from datetime import datetime, timedelta


        # print("PAIR")
            # Aliases for self-join
        start_time = time.time()
        A = aliased(ComIntDetectionEntity)
        B = aliased(ComIntDetectionEntity)
        
        # Calculate the threshold datetime
        # print(time.time()-start_time)
        threshold_time = datetime.utcnow() - timedelta(seconds=threshold_seconds)
        
        # Query to find pairs
        # query = self._db.session.query(A, B).filter(
        # print(1, time.time()-start_time)
        query = self._db.query(A, B).filter(
            and_(
                A.uav_id != B.uav_id,         # Different uav_id
                A.roi_identifier == B.roi_identifier,           # Same roi_id
                func.abs(func.extract('epoch', A.timestamp) - func.extract('epoch', B.timestamp)) < 1,  # Time difference < 1 second
                A.timestamp > threshold_time,              # A.time is more recent than threshold
                B.timestamp > threshold_time,               # B.time is more recent than threshold
            )
        )
        # .order_by(A.detection_id).order_by(
        #     -func.abs(func.extract('epoch', A.timestamp) - func.extract('epoch', B.timestamp))
        # ).limit(200)
        #.order_by(A.detection_id+B.detection_id).limit(20)
        
        # print(2, time.time()-start_time)

        # query = self._db.query(A).filter(A.detection_id == 2732191)


        # Execute and fetch results
        # return query.all()
        
        result = query.all()
        # print(3, time.time()-start_time, " len(results) =", len(result))
        def sort_func(pair):
            return pair[0].detection_id + pair[1].detection_id
        result.sort(key=sort_func)
        # print(4, time.time()-start_time)
        if len(result)>15:
            result = result[-1:]
        # print(5, time.time()-start_time)
        # print("GEOLOC DETECTIONS", len(result))
        # print(result[0][0].detection_id if len(result) else "")
        # print(result)
        

        return result
    
    def _triangulate(self, d1: ComIntDetectionEntity, d2: ComIntDetectionEntity):
        """Triangulate 2 detection azimuth values. Return the coordinates"""
        
        def triangulate_nautipy(lat1, lon1, azim1, lat2, lon2, azim2, lat_gt=.0, lon_gt=.0):
            # from pysagax.gany import nautipy
            from pysagax.analyzing_tools.old.spotclient_recordings import nautipy
            # if any(np.isnan([lat1, lon1, azim1, lat2, lon2, azim2, lat_gt, lon_gt])):
            #     return [float("nan")]*3
            # azim1 = normalize_angle(azim1*180/np.pi, 360, 0)
            # azim2 = normalize_angle(azim2*180/np.pi, 360, 0)
            # print(type(float(lat1)))
            p1 = nautipy.Pos(lat1, lon1)
            p2 =nautipy.Pos(lat2, lon2)
            target = nautipy.triangulate(p1, normalize_angle(azim1, 360, 0), p2, normalize_angle(azim2, 360, 0))

            azim1_back = nautipy.bearing(p1, target)
            azim2_back = nautipy.bearing(p2, target)
            self._logger.debug(f" a1={azim1:.2f}, a1'={azim1_back:.2f}, a2={azim2:.2f}, a2'={azim2_back:.2f} >>> f{abs(normalize_angle(azim1_back - azim1, 180, -180))>5} {abs(normalize_angle(azim2_back - azim2, 180, -180))>5}", )
            if abs(normalize_angle(azim1_back - azim1, 180, -180))>5 or abs(normalize_angle(azim2_back - azim2, 180, -180))>5:
                self._logger.debug(f"NO INTERSECITÁON a1={azim1:2f}, a1'={azim1_back}, a2={azim2:2f}, a2'={azim2_back:2f}", )
                return [float("nan")]*2 #the azimut lines dont intersect (needs to be geometrically checked)

            error = nautipy.haversine(target, nautipy.Pos(lat_gt, lon_gt)) * 1000
            return target.lat, target.lon#, error #measured lat, lon, error in meters
        
        def triangulate_geographiclib(lat1, lon1, azim1, lat2, lon2, azim2):
            import geographiclib
            pass

        def triangulate_pygeodesy(lat1, lon1, azim1, lat2, lon2, azim2):
            from pygeodesy.sphericalTrigonometry import LatLon
            LatLon(lat=lat1, lon=lon1).intersection()


        def triangulate_cgpt(lat1, lon1, azim1, lat2, lon2, azim2):
            import math
            # Convert degrees to radians
            lat1, lon1, azim1 = map(math.radians, [lat1, lon1, azim1])
            lat2, lon2, azim2 = map(math.radians, [lat2, lon2, azim2])

            # Convert azimuths to unit vector (great-circle normal vectors)
            def azimuth_to_vector(lat, lon, azim):
                x = math.cos(lat) * math.cos(lon + azim)
                y = math.cos(lat) * math.sin(lon + azim)
                z = math.sin(lat)
                return (x, y, z)

            # Compute normal vectors for the two great circles
            def cross_product(u, v):
                return (
                    u[1] * v[2] - u[2] * v[1],
                    u[2] * v[0] - u[0] * v[2],
                    u[0] * v[1] - u[1] * v[0],
                )

            def normalize(v):
                norm = math.sqrt(sum(x ** 2 for x in v))
                return tuple(x / norm for x in v)

            vec1 = azimuth_to_vector(lat1, lon1, azim1)
            vec2 = azimuth_to_vector(lat2, lon2, azim2)
            
            # Find the intersection line of the two planes
            intersection = cross_product(vec1, vec2)
            intersection = normalize(intersection)
            
            # Choose one of the two possible intersection points
            def to_latlon(vector):
                x, y, z = vector
                lat = math.atan2(z, math.sqrt(x ** 2 + y ** 2))
                lon = math.atan2(y, x)
                return math.degrees(lat), math.degrees(lon)
            
            point1 = to_latlon(intersection)
            point2 = to_latlon((-intersection[0], -intersection[1], -intersection[2]))
            
            # Determine which point is closer to the starting points
            def haversine(lat1, lon1, lat2, lon2):
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = (math.sin(dlat / 2) ** 2 +
                    math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
                return 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            
            d1 = haversine(lat1, lon1, point1[0], point1[1]) + haversine(lat2, lon2, point1[0], point1[1])
            d2 = haversine(lat1, lon1, point2[0], point2[1]) + haversine(lat2, lon2, point2[0], point2[1])
            
            return point1 if d1 < d2 else point2
        
        def triangulate_claude(lat1, lon1, azim1, lat2, lon2, azim2):
            """
            Calculate the intersection point of two bearings from two known positions using spherical trigonometry.
            
            Args:
                lat1, lon1: Position coordinates of first point (in decimal degrees)
                azim1: Bearing from first point (in decimal degrees)
                lat2, lon2: Position coordinates of second point (in decimal degrees)
                azim2: Bearing from second point (in decimal degrees)
            
            Returns:
                tuple: (intersection_lat, intersection_lon) in decimal degrees
                or None if no intersection exists or lines are parallel
            """
            import math
            # Convert to radians
            lat1 = math.radians(lat1)
            lon1 = math.radians(lon1)
            lat2 = math.radians(lat2)
            lon2 = math.radians(lon2)
            azim1 = math.radians(azim1)
            azim2 = math.radians(azim2)
            
            # Calculate the angular distance between points
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            # Calculate position on great circle
            dist_rad = 2 * math.asin(math.sqrt(
                math.sin(dlat/2)**2 + 
                math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            ))
            
            # Check if points are the same
            if dist_rad < 1e-10:
                return None
                
            # Calculate initial and final bearings between points
            initial_bearing = math.atan2(
                math.sin(dlon) * math.cos(lat2),
                math.cos(lat1) * math.sin(lat2) - 
                math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
            )
            
            # Calculate angles
            angle1 = azim1 - initial_bearing
            angle2 = azim2 - initial_bearing
            
            # Calculate intersection angle
            angle_at_intersection = math.asin(
                math.sin(angle1) * math.sin(angle2) * math.sin(dist_rad) /
                (1 - math.cos(angle1) * math.cos(angle2) * math.cos(dist_rad))
            )
            
            # Check if intersection exists
            if math.isnan(angle_at_intersection):
                return None
            
            # Calculate distance from first point to intersection
            dist_to_intersection = math.atan2(
                math.sin(dist_rad) * math.cos(angle1),
                math.cos(dist_rad) * math.sin(angle1)
            )
            
            # Calculate intersection position
            intersection_lat = math.asin(
                math.sin(lat1) * math.cos(dist_to_intersection) +
                math.cos(lat1) * math.sin(dist_to_intersection) * math.cos(azim1)
            )
            
            intersection_lon = lon1 + math.atan2(
                math.sin(azim1) * math.sin(dist_to_intersection) * math.cos(lat1),
                math.cos(dist_to_intersection) - math.sin(lat1) * math.sin(intersection_lat)
            )
            
            # Convert back to degrees
            intersection_lat = math.degrees(intersection_lat)
            intersection_lon = math.degrees(intersection_lon)
            
            return (intersection_lat, intersection_lon)

        def triangulate_claude2(lat1, lon1, azim1, lat2, lon2, azim2):
            """
            Calculate the intersection point of two bearings from two known positions on the WGS84 ellipsoid.
            
            Args:
                lat1, lon1: Position 1 coordinates in decimal degrees
                azim1: Bearing from position 1 in decimal degrees
                lat2, lon2: Position 2 coordinates in decimal degrees
                azim2: Bearing from position 2 in decimal degrees
                
            Returns:
                tuple: (latitude, longitude) of intersection point in decimal degrees
                None: if no intersection exists or lines are parallel
            """
            from math import radians, degrees, sin, cos, tan, atan2, pi, asin
            
            # Convert everything to radians
            lat1, lon1 = radians(lat1), radians(lon1)
            lat2, lon2 = radians(lat2), radians(lon2)
            azim1, azim2 = radians(azim1), radians(azim2)
            
            # Calculate differences
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            # Find distance and initial bearing between points using haversine formula
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            dist_12 = 2 * atan2(a**0.5, (1-a)**0.5)
            
            # Calculate initial bearing from point 1 to point 2
            y = sin(dlon) * cos(lat2)
            x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
            brng_12 = atan2(y, x)
            
            # Calculate angles
            angle1 = azim1 - brng_12
            angle2 = brng_12 - azim2
            
            # Check if lines are parallel or coincident
            if sin(angle1) == 0 and sin(angle2) == 0:
                return None  # Lines are parallel
            
            # Calculate angular distance from point 1 to intersection
            angle3 = atan2(sin(dist_12) * sin(angle1) * sin(angle2),
                        cos(angle2) + cos(angle1) * cos(dist_12))
            dist_13 = atan2(sin(dist_12) * sin(angle1) * sin(angle2),
                            cos(angle2) + cos(angle1) * cos(dist_12))
            
            # Find intersection point
            lat3 = asin(sin(lat1) * cos(dist_13) + 
                        cos(lat1) * sin(dist_13) * cos(azim1))
            
            dlon13 = atan2(sin(azim1) * sin(dist_13) * cos(lat1),
                        cos(dist_13) - sin(lat1) * sin(lat3))
            
            lon3 = lon1 + dlon13
            
            # Convert back to degrees
            lat3 = degrees(lat3)
            lon3 = degrees(lon3)
            
            # Normalize longitude to -180 to 180
            lon3 = ((lon3 + 180) % 360) - 180
            
            return lat3, lon3





        #TODO
        triangulate_function = triangulate_nautipy
        # triangulate_function = triangulate_claude2
        lat, lon = triangulate_function(
            float(d1.uav_pos_lat),
            float(d1.uav_pos_lon), 
            float(d1.lob_azim_deg),
            float(d2.uav_pos_lat),
            float(d2.uav_pos_lon),
            float(d2.lob_azim_deg)
        )
        # print("RESULT:", lat, lon)
        return lat, lon

    def _save_results(self, d1:ComIntDetectionEntity, d2:ComIntDetectionEntity, target_lat, target_lon):
        """Save geolocation data to DB"""

        new_geoloc = ComIntGeoLocEntity()
        # TODO: define event_id, measurement_id, etc. in table definition and fill them here
        

        new_geoloc.roi_identifier = d1.roi_identifier
        new_geoloc.lat = target_lat
        new_geoloc.lon = target_lon
        # TODO: new_geoloc.certainty_radius = ???
        time_diff = d1.timestamp - d2.timestamp
        new_geoloc.detections_time_delta = abs(time_diff)
        new_geoloc.timestamp = d2.timestamp + time_diff /2
        
        self._db.add(new_geoloc)
        self._db.commit()
   
    def _loop(self) -> None:
        time.sleep(0.1)

        with self._app.app_context():
            #WHY and WHEN do we even need this context stuff???
            detection_pair_list = self._pair_detections()

            for d_pair in detection_pair_list:
                d1, d2 = d_pair
                target_lat, target_lon = self._triangulate(d1, d2)
                self._save_results(d1, d2, target_lat, target_lon)

                # TODO: provide proper data to APMcomm.
                roi_id = 0 # TODO
                ts = 0 # TODO : type=??
                queue_put(self._apm_queue, (roi_id, ts, target_lat, target_lon),
                            0, self._logger)
        
