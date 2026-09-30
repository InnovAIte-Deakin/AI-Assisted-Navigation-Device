import React, { Suspense } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  View,
} from "react-native";
import Constants from "expo-constants";
import { router } from "expo-router";

import { PageHeader } from "@/components/ui/PageHeader";

const AskAFriendAgora = React.lazy(
  () => import("@/components/AskAFriendAgora.ios")
);

function ExpoGoNotice() {
  return (
    <View style={styles.screen}>
      <PageHeader
        title="Ask a Friend"
        onBackPress={() => router.back()}
      />
    </View>
  );
}

export default function AskAFriendIosScreen() {
  const isExpoGo =
    Constants.executionEnvironment === "storeClient";

  if (isExpoGo) {
    return <ExpoGoNotice />;
  }

  return (
    <Suspense
      fallback={
        <View style={styles.loading}>
          <ActivityIndicator size="large" />
        </View>
      }
    >
      <AskAFriendAgora />
    </Suspense>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },

  loading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});
