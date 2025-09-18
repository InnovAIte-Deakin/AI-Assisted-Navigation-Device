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
    testImplementation(libs.junit)
    androidTestImplementation(libs.ext.junit)
    androidTestImplementation(libs.espresso.core)
}