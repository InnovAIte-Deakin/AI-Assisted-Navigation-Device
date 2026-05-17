package com.example.myapplication.navigation

class IndoorGraph {

    data class Node(
        val id: String,
        val name: String,
        val floor: Int,
        val isAccessible: Boolean = true,
        val isObstacle: Boolean = false
    )

    data class Edge(
        val to: String,
        val distance: Int = 1,
        val isAccessible: Boolean = true,
        val isObstacle: Boolean = false
    )

    private val nodes: MutableMap<String, Node> = mutableMapOf()
    private val adjacency: MutableMap<String, MutableList<Edge>> = mutableMapOf()

    fun addNode(node: Node) {
        nodes[node.id] = node
        adjacency.putIfAbsent(node.id, mutableListOf())
    }

    fun addUndirectedEdge(from: String, to: String, edgeProps: Edge = Edge(to = to)) {
        require(nodes.containsKey(from) && nodes.containsKey(to)) {
            "Both nodes must exist before adding an edge."
        }
        adjacency[from]!!.add(edgeProps.copy(to = to))
        adjacency[to]!!.add(edgeProps.copy(to = from))
    }

    fun getNode(id: String): Node? = nodes[id]

    fun neighbors(id: String): List<Edge> = adjacency[id]?.toList() ?: emptyList()

    fun setNodeObstacle(nodeId: String, isObstacle: Boolean) {
        val n = nodes[nodeId] ?: return
        nodes[nodeId] = n.copy(isObstacle = isObstacle)
    }

    fun setEdgeObstacle(a: String, b: String, isObstacle: Boolean) {
        fun update(from: String, to: String) {
            val list = adjacency[from] ?: return
            for (i in list.indices) {
                if (list[i].to == to) list[i] = list[i].copy(isObstacle = isObstacle)
            }
        }
        update(a, b)
        update(b, a)
    }

    fun allNodeIds(): Set<String> = nodes.keys
}
