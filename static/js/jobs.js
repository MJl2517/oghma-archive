(function () {
  async function parseResponse(response) {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      const errorPayload = payload.error || {};
      throw new Error(errorPayload.message || payload.message || "Local operation failed.");
    }
    return payload;
  }

  async function waitForLocalJob(statusUrl) {
    const deadline = Date.now() + 30 * 60 * 1000;
    while (Date.now() < deadline) {
      const payload = await parseResponse(await fetch(statusUrl, {
        headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
      }));
      const job = payload.job || {};
      if (job.state === "succeeded") return job.result || {};
      if (job.state === "failed") {
        throw new Error(job.error?.message || "Local operation failed.");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 250));
    }
    throw new Error("Local operation timed out.");
  }

  window.startLocalJob = async function startLocalJob(url, options = {}) {
    const payload = await parseResponse(await fetch(url, options));
    if (!payload.job_id || !payload.status_url) {
      throw new Error("Local operation did not start.");
    }
    return waitForLocalJob(payload.status_url);
  };

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("form[data-local-job-form]");
    if (!form) return;
    event.preventDefault();
    const buttons = [...form.querySelectorAll("button")];
    buttons.forEach((button) => { button.disabled = true; });
    try {
      const result = await window.startLocalJob(
        event.submitter?.formAction || form.action,
        {
          method: "POST",
          body: new FormData(form),
          headers: { "Accept": "application/json", "X-Requested-With": "fetch" },
        },
      );
      if (result.ok === false) throw new Error("Local operation failed.");
    } catch {
      buttons.forEach((button) => { button.disabled = false; });
    }
  });
})();
