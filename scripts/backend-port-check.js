#!/usr/bin/env node
/* Kill anything on port 8000 before starting backend to avoid stale uvicorn. */
import kill from 'kill-port';

const PORT = 8000;
kill(PORT)
  .then(() => process.exit(0))
  .catch(() => process.exit(0));


