/**
 * Karkov Weekend service worker.
 *
 * Receives Web Push notifications from the backend and routes user clicks to
 * the most useful URL (the related event, or the chat page). Activates
 * immediately on install so users get push without a hard refresh.
 */

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: "Karkov", body: event.data ? event.data.text() : "" };
  }
  const title = payload.title || "Karkov";
  const options = {
    body: payload.body || "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    data: {
      url: payload.url || "/chat",
      icon: payload.icon || null,
    },
    tag: payload.tag || "karkov-notification",
    renotify: true,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((all) => {
      for (const client of all) {
        try {
          const url = new URL(client.url);
          if (url.pathname.startsWith(targetUrl) && "focus" in client) {
            return client.focus();
          }
        } catch {
          /* ignore */
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
      return null;
    })
  );
});
