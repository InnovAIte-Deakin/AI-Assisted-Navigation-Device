plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.example.myapplication"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.example.myapplication"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {

    implementation(libs.appcompat)
    implementation(libs.material)
    implementation(libs.activity)
    implementation(libs.constraintlayout)
    // Location services for FusedLocationProviderClient
    implementation("com.google.android.gms:play-services-location:21.3.0")
    // Google Maps
    implementation("com.google.android.gms:play-services-maps:18.2.0")
    // Google Places API (New)
    implementation("com.google.android.libraries.places:places:3.4.0")
    // Google Directions API
    implementation("com.google.maps:google-maps-services:2.2.0")
    // OSMDroid as backup mapping solution
    implementation("org.osmdroid:osmdroid-android:6.1.17")
    // PyTorch for object detection
    implementation("org.pytorch:pytorch_android_lite:1.12.2")
    implementation("org.pytorch:pytorch_android_torchvision_lite:1.12.2")
    // Add explicit native dependencies
    implementation("com.facebook.soloader:soloader:0.10.4")
    // Camera and image processing
    implementation("androidx.camera:camera-core:1.3.0")
    implementation("androidx.camera:camera-camera2:1.3.0")
    implementation("androidx.camera:camera-lifecycle:1.3.0")
    implementation("androidx.camera:camera-view:1.3.0")
    testImplementation(libs.junit)
    androidTestImplementation(libs.ext.junit)
    androidTestImplementation(libs.espresso.core)
}