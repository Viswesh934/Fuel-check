# routes/services/route_geometry.py

from math import radians, sin, cos, sqrt, atan2


EARTH_RADIUS_MILES = 3958.8


def haversine_distance(point_a, point_b):
    """
    Calculate distance between two GPS points.

    Points are represented as:
        (longitude, latitude)

    Returns distance in miles.
    """

    lon1, lat1 = point_a
    lon2, lat2 = point_b

    lat1 = radians(lat1)
    lat2 = radians(lat2)

    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return EARTH_RADIUS_MILES * c

def build_route_points(geometry, total_distance_miles=None):
    coordinates = geometry["coordinates"]

    points = []
    cumulative_miles = 0.0

    for index, coordinate in enumerate(coordinates):

        longitude = coordinate[0]
        latitude = coordinate[1]

        if index > 0:
            previous_coordinate = coordinates[index - 1]

            cumulative_miles += haversine_distance(
                previous_coordinate,
                coordinate,
            )

        points.append({
            "longitude": longitude,
            "latitude": latitude,
            "mile": cumulative_miles,
        })

    if total_distance_miles and points:
        calculated_distance = points[-1]["mile"]

        if calculated_distance > 0:
            scale = total_distance_miles / calculated_distance

            for point in points:
                point["mile"] *= scale

    return points