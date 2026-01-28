import React from "react";
import { View, Pressable, StyleSheet } from "react-native";
import Icon from "react-native-vector-icons/FontAwesome";

export default function Footer({ navigation }: any) {
  return (
    <View style={styles.footWrap}>
      <View style={styles.bottomBar}>
        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("index")}
        >
          <Icon name="home" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("camera")}
        >
          <Icon name="camera" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("indoor")}
        >
          <Icon name="building" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("exterior")}
        >
          <Icon name="road" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("audiobooks")}
        >
          <Icon name="book" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("profile")}
        >
          <Icon name="user-circle" size={30} color="#FCA311" />
        </Pressable>
        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("ask-a-friend-web")}
        >
          <Icon name="question-circle" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => navigation.navigate("places")}
        >
          <Icon name="map" size={30} color="#FCA311" />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  footWrap: {
    width: "100%",
    paddingHorizontal: 14,
    paddingBottom: 0,
    marginTop: 0,
    backgroundColor: "#0D1B2A",
  },
  bottomBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    backgroundColor: "#0D1B2A",
    borderColor: "#FCA311",
    borderRadius: 999,
    borderWidth: 2,
    paddingVertical: 22,
    paddingHorizontal: 14,
    overflow: "hidden",
    marginBottom: 20,
    marginTop: 20,
  },
  bottomItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 7,
  },
  divider: {
    width: 2,
    height: "60%",
    backgroundColor: "#FCA311",
    opacity: 0.8,
  },
});
