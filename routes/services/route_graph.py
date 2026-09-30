MAX_RANGE_MILES = 500


def build_route_nodes(candidates, route_distance):
    """
    Create the ordered nodes used by the optimizer.
    """

    nodes = [
        {
            "id": "START",
            "type": "start",
            "route_mile": 0.0,
            "station": None,
        }
    ]

    for candidate in candidates:
        station = candidate["station"]

        nodes.append({
            "id": f"STATION_{station.id}",
            "type": "station",
            "route_mile": candidate["route_mile"],
            "station": station,
            "distance_to_route": candidate["distance_to_route"],
        })

    nodes.append({
        "id": "FINISH",
        "type": "finish",
        "route_mile": route_distance,
        "station": None,
    })

    nodes.sort(
        key=lambda node: node["route_mile"]
    )

    return nodes

def build_route_graph(nodes, max_range=MAX_RANGE_MILES):
    """
    Build a forward-only graph.

    An edge exists when the next node is reachable
    within the vehicle's maximum range.
    """

    graph = {
        node["id"]: []
        for node in nodes
    }

    for i, current in enumerate(nodes):

        for j in range(i + 1, len(nodes)):

            next_node = nodes[j]

            distance = (
                next_node["route_mile"]
                - current["route_mile"]
            )

            # Nodes are sorted by route_mile,
            # so everything after this will also
            # be too far away.
            if distance > max_range:
                break

            graph[current["id"]].append({
                "to": next_node["id"],
                "distance": distance,
            })

    return graph