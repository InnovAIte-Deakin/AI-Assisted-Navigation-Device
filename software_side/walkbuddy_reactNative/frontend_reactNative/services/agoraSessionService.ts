export type AssistanceSession = {
  sessionId: string;
  appId: string;
  channelName: string;
  uid: number;
  token: string;
  inviteId: string;
  sessionSecret: string;
  expiresAt: number;
};

function getSessionApiUrl() {
  const url =
    process.env
      .EXPO_PUBLIC_AGORA_SESSION_URL ??
    "";

  if (!url) {
    throw new Error(
      "EXPO_PUBLIC_AGORA_SESSION_URL is not configured"
    );
  }

  return url.replace(/\/+$/, "");
}

function getHelperPageUrl() {
  const url =
    process.env
      .EXPO_PUBLIC_HELPER_PAGE_URL ??
    "";

  if (!url) {
    throw new Error(
      "EXPO_PUBLIC_HELPER_PAGE_URL is not configured"
    );
  }

  return url.replace(/\/+$/, "");
}

export async function createAssistanceSession():
  Promise<AssistanceSession> {

  const apiUrl =
    getSessionApiUrl();

  const response =
    await fetch(
      `${apiUrl}/api/sessions`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },
      }
    );

  if (!response.ok) {
    const body =
      await response.text();

    throw new Error(
      `Unable to create session: ${response.status} ${body}`
    );
  }

  return await response.json();
}

export function createHelperInviteUrl(
  session: AssistanceSession
) {
  const apiUrl =
    getSessionApiUrl();

  const helperPageUrl =
    getHelperPageUrl();

  return (
    `${helperPageUrl}` +
    `?invite=${encodeURIComponent(
      session.inviteId
    )}` +
    `&api=${encodeURIComponent(
      apiUrl
    )}`
  );
}

export async function endAssistanceSession(
  session: AssistanceSession
) {
  const apiUrl =
    getSessionApiUrl();

  const response =
    await fetch(
      `${apiUrl}/api/sessions/${session.sessionId}/end`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify({
            sessionSecret:
              session.sessionSecret,
          }),
      }
    );

  if (!response.ok) {
    const body =
      await response.text();

    throw new Error(
      `Unable to end session: ${response.status} ${body}`
    );
  }
}