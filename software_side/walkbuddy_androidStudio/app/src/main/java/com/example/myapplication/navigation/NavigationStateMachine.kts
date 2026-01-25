package com.example.myapplication.navigation

class NavigationStateMachine(
    private val onStateChange: (NavState, NavContext) -> Unit = { _, _ -> }
) {

    enum class NavState {
        IDLE,
        DETECTING_LOCATION,
        ROUTE_CALCULATION,
        WAYPOINT_NAVIGATION,
        DESTINATION_REACHED,
        ERROR
    }

    data class NavContext(
        val currentLocationNodeId: String? = null,
        val destinationNodeId: String? = null,
        val route: List<String> = emptyList(),
        val errorMessage: String? = null
    )

    private var state: NavState = NavState.IDLE
    private var context: NavContext = NavContext()

    fun getState(): NavState = state
    fun getContext(): NavContext = context

    private fun setState(newState: NavState, newContext: NavContext = context) {
        state = newState
        context = newContext
        onStateChange(state, context)
    }

    /** Start navigation to a destination node (e.g., library room / waypoint). */
    fun startNavigation(destinationNodeId: String) {
        setState(
            NavState.DETECTING_LOCATION,
            context.copy(destinationNodeId = destinationNodeId, errorMessage = null)
        )
    }

    /** Called when sensors (BLE/QR/NFC) provide a location update. */
    fun updateLocation(currentNodeId: String) {
        val updated = context.copy(currentLocationNodeId = currentNodeId, errorMessage = null)
        // If we were detecting, move to route calculation when we have a location
        if (state == NavState.DETECTING_LOCATION) {
            setState(NavState.ROUTE_CALCULATION, updated)
        } else {
            setState(state, updated)
        }
    }

    /** Set the computed route (list of node IDs). */
    fun setRoute(route: List<String>) {
        setState(NavState.WAYPOINT_NAVIGATION, context.copy(route = route, errorMessage = null))
    }

    /** Called when the user reaches the destination. */
    fun arrive() {
        setState(NavState.DESTINATION_REACHED, context.copy(errorMessage = null))
    }

    /** Set an error state (e.g., no route found, blocked start, etc.). */
    fun fail(errorMessage: String) {
        setState(NavState.ERROR, context.copy(errorMessage = errorMessage))
    }
}
