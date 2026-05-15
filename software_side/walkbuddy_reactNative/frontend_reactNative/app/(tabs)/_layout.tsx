import React from "react";
import { Tabs } from "expo-router";
import Footer from "../Footer";

export default function TabLayout() {
  return (
    <Tabs tabBar={(props) => <Footer {...props} />}>
      <Tabs.Screen name="index" options={{ title: "Home" }} />
      <Tabs.Screen name="audiobooks" options={{ title: "Audiobooks" }} />
      <Tabs.Screen name="ask-a-friend-web" options={{ title: "Ask" }} />
      <Tabs.Screen name="indoor" options={{ title: "Indoor" }} />
      <Tabs.Screen name="exterior" options={{ title: "Exterior" }} />
      <Tabs.Screen name="camera" options={{ title: "Camera" }} />
      <Tabs.Screen name="places" options={{ title: "Places" }} />
      <Tabs.Screen name="favourites" options={{ title: "Favourites" }} />
      <Tabs.Screen name="profile" options={{ title: "Profile", href: null }} />
      <Tabs.Screen name="emergency" options={{ title: "Emergency", href: null }} />
      <Tabs.Screen name="predictive-path" options={{ title: "Predictive Path", href: null }} />
      <Tabs.Screen name="search" options={{ title: "Search", href: null }} />
    </Tabs>
  );
}