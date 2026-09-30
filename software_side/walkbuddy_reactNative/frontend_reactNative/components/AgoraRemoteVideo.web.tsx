import React from "react";
import { View } from "react-native";

type Props = {
  uid: number;
  style?: any;
};

export function AgoraRemoteVideo({ style }: Props) {
  return <View style={style} />;
}