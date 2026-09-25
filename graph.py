# graph.py

def build_indexes(task_ids, edges):
    """
    Build prerequisite, dependent and indegree indexes.
    """

    prereqs = {task_id: [] for task_id in task_ids}
    dependents = {task_id: [] for task_id in task_ids}
    indegree = {task_id: 0 for task_id in task_ids}

    for task_id, depends_on_id in edges:
        if task_id not in prereqs or depends_on_id not in prereqs:
            continue

        prereqs[task_id].append(depends_on_id)
        dependents[depends_on_id].append(task_id)
        indegree[task_id] += 1

    return prereqs, dependents, indegree


def topological_sort(task_ids, edges):
    """
    Return tasks in dependency order.
    Return None if the graph contains a cycle.
    """

    prereqs, dependents, indegree = build_indexes(task_ids, edges)

    # Tasks with no prerequisites can be processed first.
    ready = sorted(
        task_id
        for task_id in task_ids
        if indegree[task_id] == 0
    )

    order = []

    while ready:
        current = ready.pop(0)
        order.append(current)

        for child in dependents[current]:
            indegree[child] -= 1

            if indegree[child] == 0:
                ready.append(child)

        ready.sort()

    # Not all tasks could be processed means a cycle exists.
    if len(order) != len(task_ids):
        return None

    return order


def creates_cycle(task_ids, existing_edges, new_edge):
    """
    Check whether adding a new dependency creates a cycle.
    """

    task_id, depends_on_id = new_edge

    if task_id == depends_on_id:
        return True

    proposed_edges = list(existing_edges) + [new_edge]

    return topological_sort(
        task_ids,
        proposed_edges
    ) is None