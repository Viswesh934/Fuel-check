from math import cos, hypot, radians

from .route_geometry import haversine_distance


EARTH_RADIUS_MILES = 3958.8


def to_xy(point, reference_latitude):
    """
    Convert (longitude, latitude) into a local flat coordinate system.

    The result is in miles.
    """
    longitude, latitude = point

    x = (
        EARTH_RADIUS_MILES
        * radians(longitude)
        * cos(radians(reference_latitude))
    )

    y = EARTH_RADIUS_MILES * radians(latitude)

    return x, y

def deduplicate_candidates(candidates):
    seen = set()
    unique = []

    for candidate in candidates:
        station = candidate["station"]

        key = (
            round(station.latitude, 5),
            round(station.longitude, 5),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(candidate)

    return unique

def project_point_to_segment(point, segment_start, segment_end):
    """
    Project a point onto a line segment.

    Returns:
        fraction:
            0 -> closest to segment_start
            1 -> closest to segment_end

        distance_miles:
            Distance from point to the segment.

    Points are (longitude, latitude).
    """

    reference_latitude = (
        point[1]
        + segment_start[1]
        + segment_end[1]
    ) / 3

    px, py = to_xy(point, reference_latitude)
    ax, ay = to_xy(segment_start, reference_latitude)
    bx, by = to_xy(segment_end, reference_latitude)

    dx = bx - ax
    dy = by - ay

    segment_length_squared = dx * dx + dy * dy

    if segment_length_squared == 0:
        return 0.0, hypot(px - ax, py - ay)

    t = (
        (px - ax) * dx
        + (py - ay) * dy
    ) / segment_length_squared

    # Keep projection inside the segment.
    t = max(0.0, min(1.0, t))

    closest_x = ax + t * dx
    closest_y = ay + t * dy

    distance = hypot(
        px - closest_x,
        py - closest_y,
    )

    return t, distance


def find_station_position(
    station,
    route_points,
    tolerance_miles=2.0,
):
    """
    Find where a fuel station lies along the route.

    Returns None if the station is more than tolerance_miles
    away from the route.

    Otherwise returns:

    {
        "station": station,
        "route_mile": ...,
        "distance_to_route": ...
    }
    """

    station_point = (
        station.longitude,
        station.latitude,
    )

    best_distance = float("inf")
    best_route_mile = None

    for index in range(len(route_points) - 1):
        current = route_points[index]
        next_point = route_points[index + 1]

        segment_start = (
            current["longitude"],
            current["latitude"],
        )

        segment_end = (
            next_point["longitude"],
            next_point["latitude"],
        )

        fraction, distance = project_point_to_segment(
            station_point,
            segment_start,
            segment_end,
        )

        if distance < best_distance:
            best_distance = distance

            segment_length = haversine_distance(
                segment_start,
                segment_end,
            )

            best_route_mile = (
                current["mile"]
                + fraction * segment_length
            )

    if best_distance > tolerance_miles:
        return None

    return {
        "station": station,
        "route_mile": best_route_mile,
        "distance_to_route": best_distance,
    }


def find_candidate_stations(
    stations,
    route_points,
    tolerance_miles=2.0,
):
    """
    Find all fuel stations close enough to the route.

    Returns candidates ordered by their position along the route.
    """

    candidates = []

    for station in stations:
        if station.latitude is None or station.longitude is None:
            continue

        result = find_station_position(
            station,
            route_points,
            tolerance_miles,
        )

        if result is not None:
            candidates.append(result)

    candidates.sort(
        key=lambda candidate: candidate["route_mile"]
    )

    return deduplicate_candidates(candidates)