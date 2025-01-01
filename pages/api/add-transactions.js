// pages/api/add-transactions.js
import { spawn } from "child_process";
import path from "path";

let pythonServer = null;
let serverStarting = false;

async function startPythonServer() {
  if (serverStarting) return;
  serverStarting = true;

  const serverPath = path.resolve("src/python/server.py");
  pythonServer = spawn("python3", [serverPath], {
    env: {
      ...process.env,
      PYTHONPATH: process.cwd(),
      OPENAI_API_KEY: process.env.OPENAI_API_KEY,
      PYTHON_SERVER_PORT: "3001"
    }
  });

  pythonServer.stdout.on("data", (data) => {
    console.log(`Python server: ${data}`);
  });

  pythonServer.stderr.on("data", (data) => {
    console.error(`Python server error: ${data}`);
  });

  // Wait for server to start
  await new Promise((resolve) => {
    pythonServer.stdout.on("data", (data) => {
      if (data.toString().includes("Server running")) {
        resolve();
      }
    });
  });

  serverStarting = false;
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const userQuery = req.body.query;
    if (!userQuery || typeof userQuery !== "string") {
      return res.status(400).json({ error: "Invalid query. Please provide a string query." });
    }

    // Ensure Python server is running
    if (!pythonServer) {
      await startPythonServer();
    }

    // Send request to Python server
    const response = await fetch("http://localhost:3001", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: userQuery }),
    });

    if (!response.ok) {
      throw new Error(`Python server responded with status ${response.status}`);
    }

    const result = await response.json();
    
    if (result.status === "success") {
      res.status(200).json({ assistantResponse: result.reply });
    } else {
      res.status(500).json({ error: result.message || "Unknown error from assistant." });
    }

  } catch (error) {
    console.error("Error processing request:", error);
    res.status(500).json({ error: error.message });
  }
}

// Clean up Python server on app shutdown
process.on("SIGTERM", () => {
  if (pythonServer) {
    pythonServer.kill();
  }
});
