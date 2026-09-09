/* Frontend configuration — this file is generated at build/deploy time.
   Do not edit manually unless you know the target backend URL. */
window.__APP_CONFIG__ = {
  API_BASE_URL: (() => {
    try {
      const env = process && process.env && process.env.NEXT_PUBLIC_API_BASE_URL;
      if (env) return env;
    } catch (e) {}
    const meta = document.querySelector('meta[name="api-base-url"]');
    if (meta && meta.content) return meta.content;
    return window.location.origin;
  })(),
};
