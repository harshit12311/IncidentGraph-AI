import json
import networkx as nx
from pathlib import Path


def create_dependency_graph(config_path="config/monitoring.json"):
    """Build a graph from configured applications and external websites."""

    config_file = Path(config_path)

    with config_file.open() as file:
        config = json.load(file)

    graph = nx.DiGraph()

    for application in config.get("applications", []):
        name = application["name"]

        graph.add_node(
            name,
            node_type="application",
            url=application.get("base_url")
        )

        for dependency in application.get("dependencies", []):
            graph.add_node(
                dependency,
                node_type="dependency"
            )
            graph.add_edge(
                name,
                dependency,
                relationship="depends_on"
            )

    for website in config.get("external_websites", []):
        name = website["name"]

        graph.add_node(
            name,
            node_type="external_website",
            url=website.get("url")
        )

    return graph


def find_affected_components(graph, failed_component):
    """Find components that depend on the failed component."""

    if failed_component not in graph:
        return []

    dependency_graph = nx.DiGraph()

    dependency_graph.add_nodes_from(graph.nodes(data=True))

    dependency_graph.add_edges_from(
        (source, target)
        for source, target, data in graph.edges(data=True)
        if data.get("relationship") == "depends_on"
    )

    affected = [failed_component]
    affected.extend(nx.ancestors(dependency_graph, failed_component))

    return affected


def display_graph(graph):
    print("IncidentGraph Dependency Graph")
    print("-" * 40)

    print("\nMonitored Components:")

    for name, data in graph.nodes(data=True):
        print(f"- {name} ({data.get('node_type', 'unknown')})")

    print("\nDependencies:")

    for source, target, data in graph.edges(data=True):
        print(f"{source} -> {target} [{data.get('relationship')}]")


if __name__ == "__main__":
    dependency_graph = create_dependency_graph()
    display_graph(dependency_graph)
