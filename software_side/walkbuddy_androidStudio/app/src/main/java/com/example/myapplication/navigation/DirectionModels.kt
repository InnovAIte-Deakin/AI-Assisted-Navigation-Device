data class DirectionStep(
    val action: Action,
    val distanceMeters: Int,
    val landmark: String? = null
)

enum class Action {
    START, TURN_LEFT, TURN_RIGHT, GO_STRAIGHT, ARRIVE
}