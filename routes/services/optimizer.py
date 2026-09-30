MAX_RANGE_MILES = 500
MPG = 10

def build_optimization_result(result, nodes, graph):
    if result is None:
        return None

    node_lookup = {
        node["id"]: node
        for node in nodes
    }

    path = result["path"]

    stops = []
    legs = []

    total_gallons_purchased = 0.0

    for index in range(len(path) - 1):
        current_id = path[index]
        next_id = path[index + 1]

        current_node = node_lookup[current_id]

        distance = next(
            edge["distance"]
            for edge in graph[current_id]
            if edge["to"] == next_id
        )

        gallons = 0.0
        cost = 0.0

        if current_node["type"] == "station":
            station = current_node["station"]

            gallons = distance / MPG
            cost = gallons * float(station.retail_price)

            total_gallons_purchased += gallons

            stops.append({
                "id": station.id,
                "name": station.name,
                "city": station.city,
                "state": station.state,
                "price_per_gallon": float(
                    station.retail_price
                ),
                "route_mile": round(current_node["route_mile"], 2),
                "gallons": round(gallons, 2),
                "cost": round(cost, 2),
            })

        legs.append({
            "from": current_id,
            "to": next_id,
            "distance_miles": round(distance, 2),
            "gallons": round(gallons, 2),
            "fuel_cost": round(cost, 2),
        })

    return {
        "path": path,
        "stops": stops,
        "legs": legs,
        "total_gallons_purchased": round(total_gallons_purchased, 2),
        "total_cost": round(result["cost"], 2),
    }

def optimize_route(nodes, graph):
    """
    Find the minimum-cost reachable path from START to FINISH.

    Assumption:
    - Vehicle starts with a full tank.
    - Fuel for each subsequent leg is purchased
      at the station where that leg begins.
    """

    infinity = float("inf")

    costs = {
        node["id"]: infinity
        for node in nodes
    }

    previous = {
        node["id"]: None
        for node in nodes
    }

    costs["START"] = 0.0

    node_lookup = {
        node["id"]: node
        for node in nodes
    }

    for node in nodes:

        current_id = node["id"]
        current_cost = costs[current_id]

        if current_cost == infinity:
            continue

        for edge in graph[current_id]:

            next_id = edge["to"]
            distance = edge["distance"]

            # Starting with a full tank means
            # the first leg costs nothing.
            if current_id == "START":
                fuel_cost = 0.0

            else:
                station = node_lookup[current_id]["station"]

                gallons = distance / MPG

                fuel_cost = (
                    gallons
                    * float(station.retail_price)
                )

            new_cost = current_cost + fuel_cost

            if new_cost < costs[next_id]:
                costs[next_id] = new_cost
                previous[next_id] = current_id

    if costs["FINISH"] == infinity:
        return None

    path = []

    current = "FINISH"

    while current is not None:
        path.append(current)
        current = previous[current]

    path.reverse()

    return {
        "cost": costs["FINISH"],
        "path": path,
    }