import networkx as nx


def create_dependency_graph():
    """
    Create the basic DemoShop dependency graph.
    """

    graph = nx.DiGraph()

    # Services/components
    graph.add_node("DemoShop")
    graph.add_node("Backend API")
    graph.add_node("Database")

    # Dependency relationships
    graph.add_edge("DemoShop", "Backend API")
    graph.add_edge("Backend API", "Database")

    return graph


def display_graph(graph):
    print("IncidentGraph Dependency Graph")
    print("-" * 40)

    print("\nComponents:")

    for node in graph.nodes:
        print(f"- {node}")

    print("\nDependencies:")

    for source, target in graph.edges:
        print(f"{source} -> {target}")


if __name__ == "__main__":

    dependency_graph = create_dependency_graph()

    display_graph(dependency_graph)