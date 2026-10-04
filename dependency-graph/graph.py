import networkx as nx


def create_dependency_graph():
    """
    Create the basic DemoShop dependency graph.
    """

    graph = nx.DiGraph()

    graph.add_edge("DemoShop", "Backend API")
    graph.add_edge("Backend API", "Database")

    return graph


def find_affected_components(graph, failed_component):
    """
    Find the component that failed and all components
    that depend on it.
    """

    if failed_component not in graph:
        return []

    affected = [failed_component]

    # Find components that depend on the failed component.
    dependents = list(
        nx.ancestors(graph, failed_component)
    )

    affected.extend(dependents)

    return affected


def display_graph(graph):
    print("IncidentGraph Dependency Graph")
    print("-" * 40)

    print("\nDependencies:")

    for source, target in graph.edges:
        print(f"{source} -> {target}")


if __name__ == "__main__":

    dependency_graph = create_dependency_graph()

    display_graph(dependency_graph)

    failed_component = "Database"

    affected = find_affected_components(
        dependency_graph,
        failed_component
    )

    print("\nFailure Analysis")
    print("-" * 40)
    print(f"Failed component : {failed_component}")

    print("Affected components:")

    for component in affected:
        print(f"- {component}")