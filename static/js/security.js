(() => {
  "use strict";

  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  if (!token) return;

  const unsafeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
  const originalFetch = window.fetch.bind(window);

  window.fetch = (input, init = {}) => {
    const requestMethod = input instanceof Request ? input.method : "GET";
    const method = String(init.method || requestMethod || "GET").toUpperCase();
    const requestUrl = input instanceof Request ? input.url : String(input);
    const url = new URL(requestUrl, window.location.href);

    if (url.origin === window.location.origin && unsafeMethods.has(method)) {
      const sourceHeaders = init.headers || (input instanceof Request ? input.headers : undefined);
      const headers = new Headers(sourceHeaders);
      headers.set("X-CSRF-Token", token);
      init = { ...init, headers };
    }
    return originalFetch(input, init);
  };

  document.addEventListener(
    "submit",
    (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      const method = String(form.method || "GET").toUpperCase();
      if (!unsafeMethods.has(method)) return;
      let field = form.querySelector('input[name="_csrf_token"]');
      if (!field) {
        field = document.createElement("input");
        field.type = "hidden";
        field.name = "_csrf_token";
        form.append(field);
      }
      field.value = token;
    },
    true,
  );
})();
