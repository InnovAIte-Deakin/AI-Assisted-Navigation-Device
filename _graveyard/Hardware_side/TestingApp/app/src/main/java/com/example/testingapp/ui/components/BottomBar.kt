package com.example.testingapp.ui.components

import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import com.example.testingapp.Screen

@Composable
fun BottomBar(
    current: Screen,
    onSelect: (Screen) -> Unit
) {
    NavigationBar {
        NavigationBarItem(
            selected = current == Screen.VISION,
            onClick = { onSelect(Screen.VISION) },
            label = { Text("Vision") },
            icon = {}
        )
        NavigationBarItem(
            selected = current == Screen.SENSORS,
            onClick = { onSelect(Screen.SENSORS) },
            label = { Text("Sensors") },
            icon = {}
        )
        NavigationBarItem(
            selected = current == Screen.STEPS,
            onClick = { onSelect(Screen.STEPS) },
            label = { Text("Steps") },
            icon = {}
        )
    }
}
