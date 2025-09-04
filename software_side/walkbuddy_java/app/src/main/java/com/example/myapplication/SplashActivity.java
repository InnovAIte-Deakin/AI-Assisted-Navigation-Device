package com.example.myapplication;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.widget.Button;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

public class SplashActivity extends AppCompatActivity {

    private static final int REQ_LOCATION_SPLASH = 1101;
    private TTSAnnouncer announcer;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_splash);

        announcer = new TTSAnnouncer(this);
        announcer.speak(getString(R.string.splash_tts));

        Button startButton = findViewById(R.id.btnStart);
        startButton.setOnClickListener(v -> {
            // Ask for location permission here so Home can fetch immediately
            boolean fine = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
            boolean coarse = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
            if (!fine && !coarse) {
                ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_LOCATION_SPLASH);
            } else {
                goToHome();
            }
        });
    }

    private void goToHome() {
        Intent intent = new Intent(SplashActivity.this, HomeActivity.class);
        startActivity(intent);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_LOCATION_SPLASH) {
            boolean granted = false;
            for (int r : grantResults) granted = granted || (r == PackageManager.PERMISSION_GRANTED);
            if (granted) {
                goToHome();
            } else {
                Toast.makeText(this, "Location permission helps show your current address", Toast.LENGTH_LONG).show();
                goToHome();
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (announcer != null) announcer.shutdown();
    }
}


