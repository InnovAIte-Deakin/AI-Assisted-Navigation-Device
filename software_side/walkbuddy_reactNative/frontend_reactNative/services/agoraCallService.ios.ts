import {
  ChannelProfileType,
  ClientRoleType,
  createAgoraRtcEngine,
  IRtcEngine,
} from "react-native-agora";

export type AgoraCallCallbacks = {
  onJoined: () => void;

  onRemoteUserJoined: (uid: number) => void;

  onRemoteUserLeft: (uid: number) => void;

  onFirstRemoteVideoFrame?: (
    uid: number,
    width: number,
    height: number
  ) => void;

  onError?: (
    errorCode: number,
    message?: string
  ) => void;
};

export type JoinAgoraCallOptions = {
  token: string;
  channelName: string;
  uid: number;
};

class AgoraCallService {
  private engine: IRtcEngine | null = null;

  private initialized = false;

  initialize(
    appId: string,
    callbacks: AgoraCallCallbacks
  ) {
    if (this.initialized) {
      return;
    }

    const engine = createAgoraRtcEngine();

    this.engine = engine;

    engine.initialize({
      appId,

      channelProfile:
        ChannelProfileType.ChannelProfileCommunication,
    });

    engine.registerEventHandler({
      onJoinChannelSuccess:
        (_connection, uid) => {
          console.log(
            "[Agora iOS] Joined as:",
            uid
          );

          callbacks.onJoined();
        },

      onUserJoined:
        (_connection, uid) => {
          console.log(
            "[Agora iOS] Helper joined:",
            uid
          );

          callbacks.onRemoteUserJoined(uid);
        },

      onFirstRemoteVideoFrame:
        (
          _connection,
          uid,
          width,
          height
        ) => {
          console.log(
            "[Agora iOS] Remote video:",
            uid,
            width,
            height
          );

          callbacks.onFirstRemoteVideoFrame?.(
            uid,
            width,
            height
          );
        },

      onUserOffline:
        (_connection, uid) => {
          console.log(
            "[Agora iOS] Helper left:",
            uid
          );

          callbacks.onRemoteUserLeft(uid);
        },

      onError:
        (err, message) => {
          console.log(
            "[Agora iOS] Error:",
            err,
            message
          );

          callbacks.onError?.(
            err,
            message
          );
        },
    });

    engine.enableVideo();

    // Start the local camera preview.
    engine.startPreview();

    // Agora starts with the front camera.
    // WalkBuddy should show the user's surroundings first.
    engine.switchCamera();

    this.initialized = true;
  }

  join(
    options: JoinAgoraCallOptions
  ) {
    if (!this.engine) {
      throw new Error(
        "Agora engine is not initialized"
      );
    }

    const result =
      this.engine.joinChannel(
        options.token,
        options.channelName,
        options.uid,
        {
          clientRoleType:
            ClientRoleType.ClientRoleBroadcaster,

          channelProfile:
            ChannelProfileType.ChannelProfileCommunication,

          publishMicrophoneTrack: true,

          publishCameraTrack: true,

          autoSubscribeAudio: true,

          autoSubscribeVideo: true,
        }
      );

    if (result < 0) {
      throw new Error(
        `Agora rejected joinChannel with code ${result}`
      );
    }

    return result;
  }

  setMuted(
    muted: boolean
  ) {
    this.engine?.muteLocalAudioStream(
      muted
    );
  }

  switchCamera() {
    this.engine?.switchCamera();
  }

  leave() {
    this.engine?.leaveChannel();
  }

  cleanup() {
    if (!this.engine) {
      return;
    }

    try {
      this.engine.leaveChannel();
      this.engine.stopPreview();
      this.engine.release();
    } catch (error) {
      console.log(
        "[Agora iOS] Cleanup error:",
        error
      );
    }

    this.engine = null;
    this.initialized = false;
  }
}

export const agoraCallService =
  new AgoraCallService();
