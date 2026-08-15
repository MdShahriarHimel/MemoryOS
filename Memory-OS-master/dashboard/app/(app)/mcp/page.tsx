"use client";

import { Check, Copy, Key, Puzzle, Terminal, Wrench } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { MCP_TOOLS, cursorMcpConfig } from "@/lib/mcp/catalog";
import { cn } from "@/lib/utils";

const CATEGORY_TONE: Record<string, "blue" | "purple" | "cyan" | "ok" | "default"> = {
  memory: "blue",
  context: "purple",
  temporal: "cyan",
  graph: "ok",
  sessions: "default",
};

function CopyBlock({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
        <Button variant="ghost" size="sm" onClick={copy}>
          {copied ? <Check className="h-3.5 w-3.5 text-[var(--ok)]" /> : <Copy className="h-3.5 w-3.5" />}
        </Button>
      </div>
      <pre className="mono max-h-64 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 text-[11px] leading-relaxed text-[var(--text-secondary)]">
        {text}
      </pre>
    </div>
  );
}

export default function McpPage() {
  const apiUrl = process.env.NEXT_PUBLIC_MEMORY_OS_API_URL || "http://localhost:8000";
  const repoPath = process.env.NEXT_PUBLIC_MCP_REPO_PATH || "/path/to/memory-os";
  const config = cursorMcpConfig(repoPath, apiUrl, "${MEMORY_OS_API_KEY}");
  const installCmd = "pip install -r mcp/requirements.txt";
  const runCmd = "python scripts/mcp_stdio_server.py";

  return (
    <div className="mx-auto max-w-5xl animate-fade-in">
      <PageHeader
        title="MCP Server"
        description="Connect Cursor, Claude Desktop, or VS Code to MEMORY OS via Model Context Protocol — model-independent memory tools only."
        action={<Badge tone="cyan">12 tools</Badge>}
      />

      <div className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card interactive glow="cyan" className="lg:col-span-1">
          <CardHeader>
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Terminal className="h-4 w-4 text-[var(--accent-cyan)]" />
              Quick start
            </h2>
          </CardHeader>
          <CardBody className="space-y-3 pt-0 text-xs text-[var(--text-secondary)]">
            <p>1. Start the API on <code className="mono">{apiUrl}</code></p>
            <p>2. Create an API key with memory + graph scopes</p>
            <p>3. Install MCP deps and paste config into Cursor</p>
            <Link href="/api-keys">
              <Button variant="secondary" size="sm" className="mt-2 w-full">
                <Key className="h-3.5 w-3.5" />
                API Keys
              </Button>
            </Link>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2 overflow-hidden">
          <div className="border-b border-[var(--border)] bg-gradient-to-r from-[var(--accent-cyan)]/10 to-[var(--accent-purple)]/5 px-5 py-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <Puzzle className="h-4 w-4 text-[var(--accent-purple)]" />
              Environment
            </h2>
          </div>
          <CardBody className="grid gap-2 sm:grid-cols-2">
            {[
              { k: "MEMORY_OS_API_URL", v: apiUrl },
              { k: "MEMORY_OS_API_KEY", v: "mos_… (from API Keys)" },
            ].map((row) => (
              <div key={row.k} className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/40 px-3 py-2">
                <p className="mono text-[10px] text-[var(--accent-cyan)]">{row.k}</p>
                <p className="mt-0.5 text-xs text-[var(--text-muted)]">{row.v}</p>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Wrench className="h-4 w-4" />
            Cursor MCP config
          </h2>
          <p className="text-xs text-[var(--text-muted)]">
            Replace <code className="mono">cwd</code> with your repo path and set your API key.
          </p>
        </CardHeader>
        <CardBody className="space-y-4 pt-0">
          <CopyBlock label=".cursor/mcp.json" text={config} />
          <CopyBlock label="Install" text={installCmd} />
          <CopyBlock label="Manual run (stdio)" text={runCmd} />
        </CardBody>
      </Card>

      <Card interactive>
        <CardHeader>
          <h2 className="text-sm font-semibold">Available tools</h2>
        </CardHeader>
        <CardBody className="pt-0">
          <ul className="grid gap-2 sm:grid-cols-2">
            {MCP_TOOLS.map((t, i) => (
              <li
                key={t.name}
                className={cn(
                  "rounded-lg border border-[var(--border)] bg-[var(--surface-2)]/30 p-3 opacity-0 animate-slide-up",
                )}
                style={{ animationDelay: `${Math.min(i, 8) * 40}ms`, animationFillMode: "forwards" }}
              >
                <div className="flex items-center gap-2">
                  <code className="mono text-xs font-medium text-[var(--text-primary)]">{t.name}</code>
                  <Badge tone={CATEGORY_TONE[t.category] ?? "default"}>{t.category}</Badge>
                </div>
                <p className="mt-1 text-[11px] text-[var(--text-muted)]">{t.summary}</p>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[11px] text-[var(--text-muted)]">
            Full docs: <code className="mono">docs/mcp.md</code> in the repository.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
