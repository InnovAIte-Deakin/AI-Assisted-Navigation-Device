/**
 * Read a local file URI (file://, content://, asset-library://, ...) into an
 * in-memory Blob.
 *
 * Why this exists: from Expo SDK 56 `expo/fetch` is installed as the global
 * `fetch`, and it does NOT understand React Native's proprietary
 * `FormData.append("file", { uri, type, name })` multipart shape - uploads built
 * that way reach the server with an empty body (this broke camera OCR and the
 * native voice STT upload after the SDK 56 bump). Appending a real `Blob` is the
 * WinterTC-compliant path that `expo/fetch` handles correctly.
 *
 * React Native's XMLHttpRequest can read local URIs with `responseType: "blob"`
 * (backed by the native BlobModule), which is the portable way to get the bytes
 * without pulling in expo-file-system's newer API here.
 *
 * @param uri           local file URI to read
 * @param fallbackType  MIME type to stamp on the Blob if the platform did not
 *                       infer one (some Android URIs come back with an empty type)
 */
export function uriToBlob(uri: string, fallbackType?: string): Promise<Blob> {
  return new Promise<Blob>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.responseType = "blob";
    xhr.onload = () => {
      const blob = xhr.response as Blob;
      if (fallbackType && !blob.type) {
        resolve(new Blob([blob], { type: fallbackType }));
      } else {
        resolve(blob);
      }
    };
    xhr.onerror = () => reject(new Error(`uriToBlob: failed to read ${uri}`));
    xhr.open("GET", uri, true);
    xhr.send(null);
  });
}
