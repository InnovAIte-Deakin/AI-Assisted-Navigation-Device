package com.example.myapplication.navigation

class InstructionFormatter(
    private val useSimpleLanguage: Boolean = true
) {

    fun format(steps: List<DirectionStep>): List<String> {
        if (steps.isEmpty()) return listOf("No route steps available.")

        return steps.mapIndexed { index, step ->
            val prefix = if (useSimpleLanguage) "Step ${index + 1}:" else "${index + 1}."
            val distance = formatDistance(step.distanceMeters)

            val base = when (step.action) {
                Action.START -> "Start and move forward"
                Action.TURN_LEFT -> "Turn left"
                Action.TURN_RIGHT -> "Turn right"
                Action.GO_STRAIGHT -> "Continue straight"
                Action.ARRIVE -> "You have arrived"
            }

            val landmarkText = step.landmark?.takeIf { it.isNotBlank() }?.let { lm ->
                if (useSimpleLanguage) " near $lm" else " (landmark: $lm)"
            }.orEmpty()

            "$prefix $base for $distance$landmarkText."
        }
    }

    private fun formatDistance(meters: Int): String {
        if (meters < 0) return "an unknown distance"
        return when {
            meters < 10 -> "${meters} metres"
            meters < 1000 -> "${meters} metres"
            else -> String.format("%.1f km", met
