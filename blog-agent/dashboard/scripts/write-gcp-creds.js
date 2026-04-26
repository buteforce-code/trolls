const fs = require("fs");

const json = process.env.GOOGLE_CREDENTIALS_JSON;
const target = process.env.GOOGLE_APPLICATION_CREDENTIALS || "/tmp/gcp-creds.json";

if (!json || !json.trim()) {
  console.warn(`[gcp-creds] GOOGLE_CREDENTIALS_JSON is empty — skipping write to ${target}`);
  process.exit(0);
}

try {
  JSON.parse(json);
} catch (err) {
  console.error(`[gcp-creds] GOOGLE_CREDENTIALS_JSON is not valid JSON: ${err.message}`);
  process.exit(1);
}

fs.writeFileSync(target, json, { mode: 0o600 });
console.log(`[gcp-creds] wrote credentials to ${target} (${json.length} bytes)`);
