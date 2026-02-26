// =============================================================================
// acp serve start/stop/status/logs (hardened mode)
// =============================================================================

import * as fs from "fs";
import * as path from "path";
import * as output from "../lib/output.js";
import { findSellerPid, isProcessRunning, removePidFromConfig, LOGS_DIR } from "../lib/config.js";

const SELLER_LOG_PATH = path.resolve(LOGS_DIR, "seller.log");

export async function start(): Promise<void> {
  output.warn(
    "Seller daemon start is disabled in hardened mode (no child_process execution)."
  );
  output.log(
    "Run seller runtime manually in a trusted terminal if needed: `npx tsx src/seller/runtime/seller.ts`\n"
  );
}

export async function stop(): Promise<void> {
  const pid = findSellerPid();

  if (pid === undefined) {
    output.log("  No seller process running.");
    return;
  }

  output.log(`  Stopping seller process (PID ${pid})...`);

  try {
    process.kill(pid, "SIGTERM");
  } catch (err: any) {
    output.fatal(`Failed to send SIGTERM to PID ${pid}: ${err.message}`);
  }

  let stopped = false;
  for (let i = 0; i < 10; i++) {
    const start = Date.now();
    while (Date.now() - start < 200) {
      /* wait */
    }
    if (!isProcessRunning(pid)) {
      stopped = true;
      break;
    }
  }

  if (stopped) {
    removePidFromConfig();
    output.output({ pid, status: "stopped" }, () => {
      output.log(`  Seller process (PID ${pid}) stopped.\n`);
    });
  } else {
    output.error(`Process (PID ${pid}) did not stop within 2 seconds. Try manual stop.`);
  }
}

export async function status(): Promise<void> {
  const pid = findSellerPid();
  const running = pid !== undefined;

  output.output({ running, pid: pid ?? null }, () => {
    output.heading("Seller Runtime");
    if (running) {
      output.field("Status", "Running");
      output.field("PID", pid!);
    } else {
      output.field("Status", "Not running");
    }
    output.log("");
  });
}

export async function logs(follow: boolean = false): Promise<void> {
  if (!fs.existsSync(SELLER_LOG_PATH)) {
    output.log("  No log file found.\n");
    return;
  }

  if (follow) {
    output.warn("Log follow mode is disabled in hardened mode.");
  }

  const content = fs.readFileSync(SELLER_LOG_PATH, "utf-8");
  const lines = content.split("\n");
  const last50 = lines.slice(-51).join("\n");
  if (last50.trim()) {
    output.log(last50);
  } else {
    output.log("  Log file is empty.\n");
  }
}
