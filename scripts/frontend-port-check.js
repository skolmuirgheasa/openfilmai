#!/usr/bin/env node
/* Kill anything on port 5173 before starting Vite to avoid stale dev servers. */
import kill from 'kill-port';

const PORT = 5173;
kill(PORT)
  .then(() => process.exit(0))
  .catch(() => process.exit(0));


