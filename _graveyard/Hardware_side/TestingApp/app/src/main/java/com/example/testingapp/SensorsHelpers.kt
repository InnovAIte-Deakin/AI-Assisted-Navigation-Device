package com.example.testingapp

private fun degreesToCompass(azimuthDeg: Float): String {
    // Normalize 0..360
    val d = ((azimuthDeg % 360f) + 360f) % 360f
    val dirs = listOf("N","NE","E","SE","S","SW","W","NW")
    val idx = ((d + 22.5f) / 45f).toInt() % 8
    return dirs[idx]
}

/** pitch<−15 => "Camera tilted down", pitch>15 => "tilted up", else "level" */
private fun tiltStatusFromPitch(pitchDeg: Float): String =
    when {
        pitchDeg <= -15f -> "Camera tilted down"
        pitchDeg >=  15f -> "Camera tilted up"
        else             -> "Level"
    }
