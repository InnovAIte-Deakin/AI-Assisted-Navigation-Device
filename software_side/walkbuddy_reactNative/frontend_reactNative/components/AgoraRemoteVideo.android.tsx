import React from "react";
import { RtcSurfaceView } from "react-native-agora";

type Props = {
  uid: number;
  style?: any;
};

export function AgoraRemoteVideo({ uid, style }: Props) {
  return <RtcSurfaceView style={style} canvas={{ uid }} />;
}