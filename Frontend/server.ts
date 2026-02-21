import express from "express";
import { createServer as createViteServer } from "vite";
import { createProxyMiddleware } from "http-proxy-middleware";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

async function startServer() {
  const app = express();
  const PORT = 3000;

  // Proxy all /api requests to the FastAPI backend BEFORE any body parsing
  // This ensures the request body is forwarded intact to the backend
  app.use("/api", createProxyMiddleware({
    target: BACKEND_URL,
    changeOrigin: true,
    pathRewrite: { "^/": "/api/" },
    logger: console,
  }));

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static("dist"));
    app.get("*", (req, res) => {
      res.sendFile("dist/index.html", { root: "." });
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Frontend server running on http://localhost:${PORT}`);
    console.log(`Proxying API requests to ${BACKEND_URL}`);
  });
}

startServer();
