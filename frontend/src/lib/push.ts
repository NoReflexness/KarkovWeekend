/**
 * Web Push helpers — registers the service worker and reconciles browser
 * subscriptions with the backend `/push/subscriptions` endpoint.
 *
 * The functions are deliberately defensive: they no-op cleanly in
 * environments without `Notification`/`PushManager` (older Safari, in-app
 * browsers, server-side rendering).
 */

import { api } from "@/lib/api";

const SERVICE_WORKER_PATH = "/service-worker.js";

export type PushAvailability = "available" | "insecure-context" | "unsupported";

export function pushAvailability(): PushAvailability {
  if (typeof window === "undefined") return "unsupported";
  // Browsers hide the entire Push/Service-Worker/Notification API surface on
  // insecure origins. Distinguish that from real lack of support so we can
  // tell the user to switch to https:// instead of vaguely blaming the
  // browser.
  if (window.isSecureContext === false) return "insecure-context";
  if (!("serviceWorker" in navigator)) return "unsupported";
  if (!("PushManager" in window)) return "unsupported";
  if (!("Notification" in window)) return "unsupported";
  return "available";
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (pushAvailability() !== "available") return null;
  try {
    const existing = await navigator.serviceWorker.getRegistration(SERVICE_WORKER_PATH);
    if (existing) return existing;
    return await navigator.serviceWorker.register(SERVICE_WORKER_PATH);
  } catch {
    return null;
  }
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  if (pushAvailability() !== "available") return null;
  const reg = await registerServiceWorker();
  if (!reg) return null;
  return reg.pushManager.getSubscription();
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const padded = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  // Allocate a plain ArrayBuffer so the resulting view satisfies BufferSource
  // (PushManager.subscribe rejects SharedArrayBuffer-backed views).
  const buffer = new ArrayBuffer(raw.length);
  const arr = new Uint8Array(buffer);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

function bufferToBase64Url(buf: ArrayBuffer | null): string {
  if (!buf) return "";
  const bytes = new Uint8Array(buf);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function ensureSubscribed(): Promise<PushSubscription> {
  if (pushAvailability() !== "available") {
    throw new Error("Push notifications er ikke understøttet i denne browser.");
  }
  const reg = await registerServiceWorker();
  if (!reg) throw new Error("Kunne ikke registrere service worker");

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Du afviste notifikationer i browseren.");
  }

  let subscription = await reg.pushManager.getSubscription();
  if (!subscription) {
    const { public_key } = await api.get<{ public_key: string; subject: string }>(
      "/push/vapid-public-key",
    );
    subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });
  }

  await api.post("/push/subscriptions", {
    endpoint: subscription.endpoint,
    keys: {
      p256dh: bufferToBase64Url(subscription.getKey("p256dh")),
      auth: bufferToBase64Url(subscription.getKey("auth")),
    },
    user_agent:
      typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 400) : null,
  });

  return subscription;
}

export async function unsubscribe(): Promise<void> {
  const subscription = await getCurrentSubscription();
  if (!subscription) return;
  try {
    await api.post("/push/unsubscribe", { endpoint: subscription.endpoint });
  } finally {
    await subscription.unsubscribe();
  }
}
