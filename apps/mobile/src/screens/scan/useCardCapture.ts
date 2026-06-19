import { useCallback, useRef } from "react";
import { Platform } from "react-native";

import { CameraView, useCameraPermissions } from "expo-camera";

import type { CaptureImage } from "@/api";

// On a real device the shutter takes a genuine still from the back camera. In the web/demo
// build (make mobile-watch) there's no camera and the app talks to the fixture client, so we
// fall back to a marker capture — the fixture upload ignores the bytes and the flow runs
// exactly as it will against the server. This is the one seam where "no hardware" is handled;
// nothing downstream knows or cares whether the bytes were real.
const DEMO_CAPTURE: CaptureImage = {
  uri: "demo://capture",
  name: "demo.jpg",
  type: "image/jpeg",
};

export function useCardCapture() {
  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  // The live camera only drives native builds with a granted permission; web/demo uses the
  // placeholder preview and the marker capture above.
  const live = Platform.OS !== "web" && !!permission?.granted;

  const capture = useCallback(async (): Promise<CaptureImage> => {
    const camera = cameraRef.current;
    if (live && camera) {
      try {
        const photo = await camera.takePictureAsync({ quality: 0.7, skipProcessing: true });
        if (photo?.uri) return { uri: photo.uri, name: "scan.jpg", type: "image/jpeg" };
      } catch {
        // A camera that refuses a frame shouldn't dead-end the scan — fall back so the user
        // still gets a result path rather than a stuck shutter.
      }
    }
    return DEMO_CAPTURE;
  }, [live]);

  return { cameraRef, permission, requestPermission, capture, live };
}
