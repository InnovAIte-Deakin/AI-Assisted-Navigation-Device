require("dotenv").config();

const express = require("express");
const cors = require("cors");
const crypto = require("crypto");

const {
  RtcTokenBuilder,
  RtcRole,
} = require("agora-access-token");


const app = express();

app.use(cors());
app.use(express.json());


const PORT =
  Number(process.env.PORT) || 3001;

const APP_ID =
  process.env.AGORA_APP_ID;

const APP_CERTIFICATE =
  process.env.AGORA_APP_CERTIFICATE;


if (!APP_ID || !APP_CERTIFICATE) {
  console.error(
    "Missing AGORA_APP_ID or AGORA_APP_CERTIFICATE in .env"
  );

  process.exit(1);
}


/*
  In-memory session store.

  Fine for our current prototype/testing.
  Later we can move this to Redis/DB if needed.
*/
const sessions =
  new Map();


function createId(bytes = 16) {
  return crypto
    .randomBytes(bytes)
    .toString("hex");
}


function createChannelName() {
  return `walkbuddy_${createId(10)}`;
}


function createUid() {
  return crypto
    .randomInt(
      100000,
      999999999
    );
}


function createRtcToken(
  channelName,
  uid,
  expirySeconds = 3600
) {
  const currentTimestamp =
    Math.floor(
      Date.now() / 1000
    );

  const privilegeExpiredTs =
    currentTimestamp +
    expirySeconds;

  return RtcTokenBuilder
    .buildTokenWithUid(
      APP_ID,
      APP_CERTIFICATE,
      channelName,
      uid,
      RtcRole.PUBLISHER,
      privilegeExpiredTs
    );
}


/*
  --------------------------------------------------
  CREATE SESSION
  WalkBuddy user calls this first.
  --------------------------------------------------
*/

app.post(
  "/api/sessions",
  (req, res) => {
    try {
      const sessionId =
        createId();

      const inviteId =
        createId(12);

      const sessionSecret =
        createId(24);

      const channelName =
        createChannelName();

      const userUid =
        createUid();

      const token =
        createRtcToken(
          channelName,
          userUid
        );

      const expiresAt =
        Date.now() +
        60 * 60 * 1000;


      const session = {
        sessionId,
        inviteId,
        sessionSecret,

        channelName,

        userUid,

        helperUid: null,

        helperClaimed: false,

        active: true,

        createdAt:
          Date.now(),

        expiresAt,
      };


      sessions.set(
        sessionId,
        session
      );


      res.status(201).json({
        sessionId,

        appId:
          APP_ID,

        channelName,

        uid:
          userUid,

        token,

        inviteId,

        sessionSecret,

        expiresAt,
      });

    } catch (error) {
      console.error(
        "[SessionServer] create error:",
        error
      );

      res.status(500).json({
        error:
          "Unable to create assistance session",
      });
    }
  }
);


/*
  --------------------------------------------------
  FIND SESSION BY INVITE
  Helper page can check whether invite exists.
  --------------------------------------------------
*/

app.get(
  "/api/sessions/invite/:inviteId",
  (req, res) => {
    const inviteId =
      req.params.inviteId;


    const session =
      Array
        .from(
          sessions.values()
        )
        .find(
          item =>
            item.inviteId ===
            inviteId
        );


    if (!session) {
      return res
        .status(404)
        .json({
          error:
            "Invitation not found",
        });
    }


    if (
      !session.active ||
      Date.now() >
        session.expiresAt
    ) {
      return res
        .status(410)
        .json({
          error:
            "Invitation expired",
        });
    }


    res.json({
      active:
        session.active,

      helperClaimed:
        session.helperClaimed,

      expiresAt:
        session.expiresAt,
    });
  }
);


/*
  --------------------------------------------------
  CLAIM HELPER INVITATION
  Only one helper at a time.
  --------------------------------------------------
*/

app.post(
  "/api/sessions/invite/:inviteId/claim",
  (req, res) => {
    try {
      const inviteId =
        req.params.inviteId;


      const session =
        Array
          .from(
            sessions.values()
          )
          .find(
            item =>
              item.inviteId ===
              inviteId
          );


      if (!session) {
        return res
          .status(404)
          .json({
            error:
              "Invitation not found",
          });
      }


      if (
        !session.active ||
        Date.now() >
          session.expiresAt
      ) {
        return res
          .status(410)
          .json({
            error:
              "Session has ended",
          });
      }


      if (
        session.helperClaimed
      ) {
        return res
          .status(409)
          .json({
            error:
              "A helper is already connected",
          });
      }


      const helperUid =
        createUid();


      const helperToken =
        createRtcToken(
          session.channelName,
          helperUid
        );


      session.helperUid =
        helperUid;

      session.helperClaimed =
        true;


      res.json({
        appId:
          APP_ID,

        sessionId:
          session.sessionId,

        channelName:
          session.channelName,

        uid:
          helperUid,

        token:
          helperToken,

        expiresAt:
          session.expiresAt,
      });

    } catch (error) {
      console.error(
        "[SessionServer] claim error:",
        error
      );

      res.status(500).json({
        error:
          "Unable to claim invitation",
      });
    }
  }
);


/*
  --------------------------------------------------
  HELPER LEAVES

  Important:
  session stays alive.
  Another helper may then be invited.
  --------------------------------------------------
*/

app.post(
  "/api/sessions/:sessionId/helper-left",
  (req, res) => {
    const session =
      sessions.get(
        req.params.sessionId
      );


    if (!session) {
      return res
        .status(404)
        .json({
          error:
            "Session not found",
        });
    }


    if (!session.active) {
      return res
        .status(410)
        .json({
          error:
            "Session has ended",
        });
    }


    session.helperUid =
      null;

    session.helperClaimed =
      false;


    res.json({
      success: true,
    });
  }
);


/*
  --------------------------------------------------
  SESSION STATUS

  Helper page polls this so the helper gets kicked
  out if the WalkBuddy user ends the call.
  --------------------------------------------------
*/

app.get(
  "/api/sessions/:sessionId/status",
  (req, res) => {
    const session =
      sessions.get(
        req.params.sessionId
      );


    if (!session) {
      return res
        .status(404)
        .json({
          active: false,
        });
    }


    const expired =
      Date.now() >
      session.expiresAt;


    if (expired) {
      session.active =
        false;
    }


    res.json({
      active:
        session.active,

      expiresAt:
        session.expiresAt,
    });
  }
);


/*
  --------------------------------------------------
  WALKbuddy USER ENDS SESSION

  This ends the call for everyone.
  --------------------------------------------------
*/

app.post(
  "/api/sessions/:sessionId/end",
  (req, res) => {
    const session =
      sessions.get(
        req.params.sessionId
      );


    if (!session) {
      return res
        .status(404)
        .json({
          error:
            "Session not found",
        });
    }


    const {
      sessionSecret,
    } =
      req.body || {};


    if (
      sessionSecret !==
      session.sessionSecret
    ) {
      return res
        .status(403)
        .json({
          error:
            "Invalid session secret",
        });
    }


    session.active =
      false;

    session.helperClaimed =
      false;

    session.helperUid =
      null;


    res.json({
      success: true,
    });
  }
);


/*
  --------------------------------------------------
  HEALTH CHECK
  --------------------------------------------------
*/

app.get(
  "/health",
  (req, res) => {
    res.json({
      ok: true,
    });
  }
);


app.listen(
  PORT,
  () => {
    console.log("");
    console.log(
      "========================================"
    );
    console.log(
      " WalkBuddy Agora Session Server"
    );
    console.log(
      "========================================"
    );
    console.log(
      `Listening on http://localhost:${PORT}`
    );
    console.log(
      `Agora App ID: ${APP_ID}`
    );
    console.log(
      "========================================"
    );
    console.log("");
  }
);