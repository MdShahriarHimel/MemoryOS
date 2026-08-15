"use client";

import { useQuery } from "@tanstack/react-query";
import { Maximize2, Network, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api/client";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

interface Node { id: string; label: string; type: string; x: number; y: number; vx: number; vy: number; }
interface Edge { source: string; target: string; rel: string; confidence: number; }

const TYPE_COLOR: Record<string, string> = {
  Person: "#3b82f6", Organization: "#8b5cf6", Project: "#22d3ee",
  Concept: "#34d399", Technology: "#fbbf24", Location: "#f87171",
};

export default function KnowledgeGraphPage() {
  const q = useQuery({ queryKey: ["graph"], queryFn: () => api.getGraph(2, 300) });
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selected, setSelected] = useState<Node | null>(null);
  const stateRef = useRef<{ nodes: Node[]; edges: Edge[]; scale: number; ox: number; oy: number }>({
    nodes: [], edges: [], scale: 1, ox: 0, oy: 0,
  });

  const resetView = useCallback(() => {
    stateRef.current.scale = 1;
    stateRef.current.ox = 0;
    stateRef.current.oy = 0;
  }, []);

  const zoom = useCallback((factor: number) => {
    stateRef.current.scale = Math.max(0.3, Math.min(3, stateRef.current.scale * factor));
  }, []);

  useEffect(() => {
    if (!q.data) return;
    const nodes: Node[] = q.data.nodes.map((n, i) => ({
      id: n.id, label: n.label, type: n.entity_type,
      x: Math.cos((i / Math.max(q.data!.nodes.length, 1)) * Math.PI * 2) * 160 + (Math.random() - 0.5) * 40,
      y: Math.sin((i / Math.max(q.data!.nodes.length, 1)) * Math.PI * 2) * 160 + (Math.random() - 0.5) * 40,
      vx: 0, vy: 0,
    }));
    const edges: Edge[] = q.data.edges.map((e) => ({
      source: e.source_id, target: e.target_id, rel: e.rel_type, confidence: e.confidence,
    }));
    stateRef.current = { ...stateRef.current, nodes, edges };
  }, [q.data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas!.getBoundingClientRect();
      canvas!.width = rect.width * dpr;
      canvas!.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    let ticks = 0;
    function step() {
      const st = stateRef.current;
      const { nodes, edges } = st;
      const w = canvas!.clientWidth, h = canvas!.clientHeight;

      if (!reduce || ticks < 120) {
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const a = nodes[i], b = nodes[j];
            const dx = a.x - b.x, dy = a.y - b.y;
            const d2 = dx * dx + dy * dy || 0.01;
            const rep = 1400 / d2;
            const d = Math.sqrt(d2);
            a.vx += (dx / d) * rep; a.vy += (dy / d) * rep;
            b.vx -= (dx / d) * rep; b.vy -= (dy / d) * rep;
          }
        }
        const byId = new Map(nodes.map((n) => [n.id, n]));
        for (const e of edges) {
          const a = byId.get(e.source), b = byId.get(e.target);
          if (!a || !b) continue;
          const dx = b.x - a.x, dy = b.y - a.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
          const spring = (d - 90) * 0.02;
          a.vx += (dx / d) * spring; a.vy += (dy / d) * spring;
          b.vx -= (dx / d) * spring; b.vy -= (dy / d) * spring;
        }
        for (const n of nodes) {
          n.vx -= n.x * 0.0008; n.vy -= n.y * 0.0008;
          n.x += n.vx * 0.1; n.y += n.vy * 0.1;
          n.vx *= 0.82; n.vy *= 0.82;
        }
        ticks++;
      }

      ctx.clearRect(0, 0, w, h);

      // Subtle grid
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.02)";
      ctx.lineWidth = 1;
      const grid = 40 * st.scale;
      for (let x = (w / 2 + st.ox) % grid; x < w; x += grid) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      }
      for (let y = (h / 2 + st.oy) % grid; y < h; y += grid) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }
      ctx.restore();

      ctx.save();
      ctx.translate(w / 2 + st.ox, h / 2 + st.oy);
      ctx.scale(st.scale, st.scale);

      const byId2 = new Map(nodes.map((n) => [n.id, n]));
      for (const e of edges) {
        const a = byId2.get(e.source), b = byId2.get(e.target);
        if (!a || !b) continue;
        const isHighlighted = selected && (e.source === selected.id || e.target === selected.id);
        ctx.strokeStyle = isHighlighted
          ? "rgba(34, 211, 238, 0.6)"
          : `rgba(148,163,184,${0.12 + e.confidence * 0.4})`;
        ctx.lineWidth = isHighlighted ? 2 : 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }

      for (const n of nodes) {
        const color = TYPE_COLOR[n.type] ?? "#94a3b8";
        const isSelected = selected?.id === n.id;
        const radius = isSelected ? 9 : 6;

        if (isSelected) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, radius + 6, 0, Math.PI * 2);
          ctx.fillStyle = `${color}22`;
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        if (isSelected) {
          ctx.strokeStyle = "#fff";
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        if (isSelected || st.scale > 0.7) {
          ctx.fillStyle = isSelected ? "rgba(230,237,246,0.95)" : "rgba(230,237,246,0.6)";
          ctx.font = `${isSelected ? 11 : 10}px Inter, sans-serif`;
          ctx.fillText(n.label.slice(0, 22), n.x + radius + 4, n.y + 4);
        }
      }
      ctx.restore();
      raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);

    let dragging = false, lastX = 0, lastY = 0;
    function toWorld(mx: number, my: number) {
      const st = stateRef.current;
      const w = canvas!.clientWidth, h = canvas!.clientHeight;
      return { x: (mx - w / 2 - st.ox) / st.scale, y: (my - h / 2 - st.oy) / st.scale };
    }
    function onDown(ev: MouseEvent) {
      dragging = true; lastX = ev.offsetX; lastY = ev.offsetY;
      const p = toWorld(ev.offsetX, ev.offsetY);
      const hit = stateRef.current.nodes.find((n) => Math.hypot(n.x - p.x, n.y - p.y) < 12);
      setSelected(hit ?? null);
    }
    function onMove(ev: MouseEvent) {
      if (!dragging) return;
      stateRef.current.ox += ev.offsetX - lastX;
      stateRef.current.oy += ev.offsetY - lastY;
      lastX = ev.offsetX; lastY = ev.offsetY;
    }
    function onUp() { dragging = false; }
    function onWheel(ev: WheelEvent) {
      ev.preventDefault();
      zoom(ev.deltaY < 0 ? 1.08 : 0.92);
    }
    canvas.addEventListener("mousedown", onDown);
    canvas.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousedown", onDown);
      canvas.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      canvas.removeEventListener("wheel", onWheel);
    };
  }, [q.data, selected, zoom]);

  const nodeCount = q.data?.nodes.length ?? 0;
  const edgeCount = q.data?.edges.length ?? 0;

  return (
    <div className="mx-auto max-w-6xl animate-fade-in">
      <PageHeader
        title="Knowledge Graph"
        description="Entities and relationships from your memories. Drag to pan, scroll to zoom, click nodes to inspect."
        action={
          q.data && (
            <div className="flex gap-2">
              <Badge tone="blue">{nodeCount} nodes</Badge>
              <Badge tone="purple">{edgeCount} edges</Badge>
            </div>
          )
        }
      />

      {q.isLoading ? (
        <LoadingState label="Loading graph" />
      ) : q.error ? (
        <ErrorState message="Could not load the graph." onRetry={() => q.refetch()} />
      ) : q.data && q.data.nodes.length === 0 ? (
        <EmptyState title="No relationships in scope" hint="Create graph edges via the API or memory metadata." icon={Network} />
      ) : (
        <Card className="overflow-hidden gradient-border">
          <div className="relative">
            <canvas
              ref={canvasRef}
              className="h-[560px] w-full cursor-grab active:cursor-grabbing bg-[var(--surface-1)]"
              role="img"
              aria-label="Interactive knowledge graph"
            />

            {/* Controls */}
            <div className="absolute left-4 top-4 flex flex-col gap-1.5">
              <Button variant="secondary" size="sm" onClick={() => zoom(1.2)} aria-label="Zoom in">
                <ZoomIn className="h-4 w-4" />
              </Button>
              <Button variant="secondary" size="sm" onClick={() => zoom(0.85)} aria-label="Zoom out">
                <ZoomOut className="h-4 w-4" />
              </Button>
              <Button variant="secondary" size="sm" onClick={resetView} aria-label="Reset view">
                <RotateCcw className="h-4 w-4" />
              </Button>
            </div>

            {/* Selected node panel */}
            {selected && (
              <Card className="absolute right-4 top-4 w-64 animate-scale-in border-[var(--accent-cyan)]/30 bg-[var(--surface-2)]/95 backdrop-blur-md">
                <CardBody>
                  <div className="flex items-start gap-3">
                    <div
                      className="h-3 w-3 shrink-0 rounded-full mt-1"
                      style={{ background: TYPE_COLOR[selected.type] ?? "#94a3b8" }}
                    />
                    <div>
                      <p className="text-sm font-semibold text-[var(--text-primary)]">{selected.label}</p>
                      <Badge tone="cyan" className="mt-2">{selected.type}</Badge>
                      <p className="mono mt-2 text-[10px] text-[var(--text-muted)] break-all">{selected.id}</p>
                    </div>
                  </div>
                </CardBody>
              </Card>
            )}

            {/* Legend */}
            <div className="absolute bottom-4 left-4 right-4 flex flex-wrap items-center justify-between gap-3">
              <Card className="border-[var(--border)]/80 bg-[var(--surface-2)]/90 px-3 py-2 backdrop-blur-md">
                <div className="flex flex-wrap gap-3 text-[11px]">
                  {Object.entries(TYPE_COLOR).map(([t, c]) => (
                    <span key={t} className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                      <span className="h-2.5 w-2.5 rounded-full ring-1 ring-white/10" style={{ background: c }} />
                      {t}
                    </span>
                  ))}
                </div>
              </Card>
              <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
                <Maximize2 className="h-3 w-3" />
                Scroll to zoom · Drag to pan
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
