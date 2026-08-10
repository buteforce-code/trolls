# Trolls — one image, two runtimes.
#
# This is deliberately not a Nixpacks/buildpack deploy. The Node server is also
# the job runner: `/api/run` calls `spawn('python', ['run.py', ...])` and the
# agent pipeline then runs for several minutes as a child of the web process.
# An auto-detected build sees `package.json`, produces a Node-only image, and
# the app then fails at *runtime* with ENOENT on `python` — which reads as an
# application bug rather than a missing interpreter.
#
# Being explicit also keeps the deploy portable: the same image runs on Railway,
# Fly, a Hetzner box or plain Docker, so the hosting choice stays reversible.

FROM node:22-bookworm-slim

# ca-certificates is needed for outbound TLS to the LLM, Supabase and Tavily.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# A virtualenv rather than a system `pip install`: Debian bookworm marks its
# system Python externally-managed (PEP 668), so installing into it fails
# outright. PYTHON_BIN is what lib/python.ts spawns, so it points here.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHON_BIN="$VIRTUAL_ENV/bin/python"

# Dependencies before source, so a code-only change does not reinstall either
# toolchain — the Python layer in particular is slow and rarely moves.
COPY blog-agent/requirements.txt ./blog-agent/requirements.txt
RUN pip install --no-cache-dir -r blog-agent/requirements.txt

COPY blog-agent/dashboard/package.json blog-agent/dashboard/package-lock.json ./blog-agent/dashboard/
RUN cd blog-agent/dashboard && npm ci

COPY . .

# `next build` reads env at build time and lib/supabase.ts calls createClient at
# module scope, which throws on an empty URL. The platform's environment
# variables must therefore be set BEFORE the first deploy, not after it.
RUN cd blog-agent/dashboard && npm run build

ENV NODE_ENV=production
WORKDIR /app/blog-agent/dashboard

# `next start` binds to $PORT when the platform injects one and 3000 otherwise.
# It is not given an explicit -p because shell-expansion syntax in an npm script
# is not portable to the Windows dev machine this repo is edited on.
EXPOSE 3000
CMD ["npm", "run", "start"]
