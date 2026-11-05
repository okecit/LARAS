"use client";

import cytoscape, { type Core, type ElementDefinition, type StylesheetJson } from "cytoscape";
// @ts-expect-error - tanpa deklarasi tipe
import fcose from "cytoscape-fcose";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from "react";
import { useTheme, type Palette } from "@/lib/theme";
import { communityColor, CONTEXT_COLORS, EVIDENCE_COLORS, PLATFORM_COLORS } from "@/lib/format";
import type { GEdge, GNode, MetricKey } from "@/lib/types";

let registered = false;
if (typeof window !== "undefined" && !registered) {
  cytoscape.use(fcose);
  registered = true;
}

export type ColorMode = "komunitas" | "platform" | "kategori" | "konteks";

export type CytoHandle = {
  png: () => string | null;
  fit: () => void;
  relayout: () => void;
  focus: (id: string) => void;
  zoom: (factor: number) => void;
};

type Props = {
  nodes: GNode[];
  edges: GEdge[];
  sizeMetric: MetricKey;
  colorMode: ColorMode;
  categoryColors: Record<string, string>;
  selectedId: string | null;
  pathIds: string[];
  search: string;
  onSelect: (id: string | null, kind: "node" | "edge" | null) => void;
  onNodeDoubleClick?: (id: string) => void;
};

function nodeColor(n: GNode, mode: ColorMode, catColors: Record<string, string>) {
  if (mode === "platform") return PLATFORM_COLORS[n.platform] || "#94A3B8";
  if (mode === "kategori") return n.categories?.[0] ? catColors[n.categories[0]] || "#94A3B8" : "#475569";
  if (mode === "konteks") return CONTEXT_COLORS[n.context_label || ""] || "#64748B";
  return communityColor(n.community);
}

export const CytoGraph = forwardRef<CytoHandle, Props>(function CytoGraph(
  { nodes, edges, sizeMetric, colorMode, categoryColors, selectedId, pathIds, search, onSelect, onNodeDoubleClick },
  ref,
) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onDblRef = useRef(onNodeDoubleClick);
  onDblRef.current = onNodeDoubleClick;
  const { palette } = useTheme();
  const paletteRef = useRef(palette);
  paletteRef.current = palette;

  const structureKey = useMemo(() => `${nodes.map((n) => n.id).join("|")}#${edges.length}`, [nodes, edges]);

  const elements = useMemo<ElementDefinition[]>(() => {
    const vals = nodes.map((n) => n.metrics?.[sizeMetric] ?? 0);
    const max = Math.max(...vals, 1e-9);
    const els: ElementDefinition[] = nodes.map((n) => {
      const v = (n.metrics?.[sizeMetric] ?? 0) / max;
      return {
        group: "nodes",
        data: {
          id: n.id, label: n.label, kind: n.kind, size: 10 + Math.sqrt(v) * 38,
          color: nodeColor(n, colorMode, categoryColors), platform: n.platform,
        },
      };
    });
    const maxW = Math.max(...edges.map((e) => e.weight), 1);
    for (const e of edges) {
      els.push({
        group: "edges",
        data: {
          id: e.id, source: e.source, target: e.target, weight: e.weight,
          width: 0.6 + (e.weight / maxW) * 5,
          color: e.evidence_status ? EVIDENCE_COLORS[e.evidence_status] : palette.edge,
          sim: e.similarity_only ? 1 : 0,
        },
      });
    }
    return els;
  }, [nodes, edges, sizeMetric, colorMode, categoryColors, palette]);

  // inisialisasi sekali
  useEffect(() => {
    if (!container.current) return;
    const style = makeStyle(paletteRef.current);
    const cy = cytoscape({
      container: container.current, style, minZoom: 0.08, maxZoom: 5, wheelSensitivity: 0.25,
      boxSelectionEnabled: false, pixelRatio: "auto",
    });
    cy.on("tap", "node", (e) => onSelectRef.current(e.target.id(), "node"));
    cy.on("tap", "edge", (e) => onSelectRef.current(e.target.id(), "edge"));
    cy.on("tap", (e) => e.target === cy && onSelectRef.current(null, null));
    cy.on("dbltap", "node", (e) => onDblRef.current?.(e.target.id()));
    cy.on("mouseover", "node", (e) => {
      const nb = e.target.closedNeighborhood();
      cy.elements().not(nb).addClass("faded");
      nb.addClass("hl");
    });
    cy.on("mouseout", "node", () => cy.elements().removeClass("faded hl"));
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // tema berubah → ganti stylesheet tanpa layout ulang
  useEffect(() => {
    cyRef.current?.style(makeStyle(palette));
  }, [palette]);

  // struktur berubah → ganti elemen & layout ulang
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().remove();
      cy.add(elements);
    });
    runLayout(cy);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structureKey]);

  // gaya (ukuran/warna) berubah tanpa layout ulang
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      for (const el of elements) {
        const c = cy.getElementById(el.data.id as string);
        if (c.nonempty()) c.data(el.data);
      }
    });
  }, [elements]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().unselect();
    if (selectedId) cy.getElementById(selectedId).select();
  }, [selectedId, structureKey]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("path");
    if (pathIds.length > 1) {
      pathIds.forEach((id, i) => {
        cy.getElementById(id).addClass("path");
        if (i < pathIds.length - 1) cy.edges(`[source = "${pathIds[i]}"][target = "${pathIds[i + 1]}"], [source = "${pathIds[i + 1]}"][target = "${pathIds[i]}"]`).addClass("path");
      });
    }
  }, [pathIds, structureKey]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("match");
    const q = search.trim().toLowerCase();
    if (q.length < 2) return;
    const hits = cy.nodes().filter((n) => String(n.data("label")).toLowerCase().includes(q));
    hits.addClass("match");
    if (hits.nonempty() && hits.length <= 12) cy.animate({ fit: { eles: hits.closedNeighborhood(), padding: 80 }, duration: 350 });
  }, [search, structureKey]);

  useImperativeHandle(ref, () => ({
    png: () => cyRef.current?.png({ full: true, scale: 2, bg: paletteRef.current.bg }) ?? null,
    fit: () => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 40 }, duration: 300 }),
    relayout: () => cyRef.current && runLayout(cyRef.current),
    focus: (id: string) => {
      const cy = cyRef.current;
      const el = cy?.getElementById(id);
      if (cy && el && el.nonempty()) cy.animate({ fit: { eles: el.closedNeighborhood(), padding: 90 }, duration: 350 });
    },
    zoom: (f: number) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.animate({ zoom: { level: cy.zoom() * f, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }, duration: 150 });
    },
  }));

  return <div ref={container} className="h-full w-full" />;
});

function makeStyle(p: Palette): StylesheetJson {
return [
    {
      selector: "node",
      style: {
        width: "data(size)", height: "data(size)", "background-color": "data(color)", "background-opacity": 0.92,
        "border-width": 1, "border-color": p.nodeBorder, label: "", color: p.label, "font-size": 8,
        "text-valign": "bottom", "text-margin-y": 3, "text-outline-color": p.bg, "text-outline-width": 2,
        "transition-property": "opacity, border-width", "transition-duration": 150,
      },
    },
    { selector: "node[kind = 'konten']", style: { shape: "round-rectangle" } },
    { selector: "node[size > 26]", style: { label: "data(label)" } },
    {
      selector: "edge",
      style: {
        width: "data(width)", "line-color": "data(color)", "target-arrow-color": "data(color)", "target-arrow-shape": "triangle",
        "arrow-scale": 0.7, "curve-style": "bezier", opacity: 0.55,
      },
    },
    { selector: "edge[sim = 1]", style: { "line-style": "dashed", "line-dash-pattern": [4, 4], "target-arrow-shape": "none", opacity: 0.45 } },
    { selector: ".faded", style: { opacity: 0.08 } },
    { selector: "node.hl", style: { label: "data(label)", "border-width": 2, "border-color": p.highlight, opacity: 1 } },
    { selector: "edge.hl", style: { opacity: 0.95 } },
    { selector: "node.match", style: { label: "data(label)", "border-width": 3, "border-color": "#FBBF24" } },
    { selector: "node.path", style: { label: "data(label)", "border-width": 3, "border-color": "#22D3EE", opacity: 1 } },
    { selector: "edge.path", style: { "line-color": "#22D3EE", "target-arrow-color": "#22D3EE", width: 4, opacity: 1 } },
    { selector: "node:selected", style: { label: "data(label)", "border-width": 3, "border-color": p.accent, "font-size": 10, color: p.ink } },
    { selector: "edge:selected", style: { "line-color": p.accent, "target-arrow-color": p.accent, opacity: 1 } },
];
}

function runLayout(cy: Core) {
  const n = cy.nodes().length;
  cy.layout({
    name: "fcose",
    quality: n > 400 ? "draft" : "default",
    randomize: true,
    animate: n < 350,
    animationDuration: 600,
    nodeRepulsion: () => 6500,
    idealEdgeLength: () => 60,
    edgeElasticity: () => 0.45,
    gravity: 0.3,
    numIter: 2500,
    padding: 30,
    nodeSeparation: 60,
  } as unknown as cytoscape.LayoutOptions).run();
}
