export type Metrics = {
  in_degree: number;
  out_degree: number;
  betweenness: number;
  closeness: number;
  pagerank: number;
  degree: number;
};
export type MetricKey = keyof Metrics;

export type GNode = {
  id: string;
  label: string;
  kind: "aktor" | "konten";
  platform: string;
  categories: string[];
  community: number;
  metrics: Partial<Metrics>;
  account_category?: string;
  follower_bucket?: string;
  context_label?: string;
  content_type?: string;
  published_at?: string;
  actor?: string;
  scenario?: string | null;
};

export type GEdge = {
  id: string;
  source: string;
  target: string;
  weight: number;
  types: string[];
  count?: number;
  relation_type?: string;
  evidence_status?: string;
  documented?: boolean;
  confidence?: number;
  similarity_only?: boolean;
};

export type NetSummary = {
  nodes: number;
  edges: number;
  density: number;
  weak_components: number;
  strong_components: number;
  largest_component_size: number;
  largest_component_share: number;
  reciprocity: number;
  modularity: number | null;
  communities: number | null;
  total_weight: number;
};

export type CommunityProfile = {
  id: number;
  size: number;
  internal_density: number;
  internal_weight: number;
  external_weight: number;
  categories: Record<string, number>;
  platforms: Record<string, number>;
  bridge_nodes?: { id: string; label: string; betweenness: number }[];
  account_categories?: Record<string, number>;
  contexts?: Record<string, number>;
};

export type GraphResponse = {
  layer: string;
  nodes: GNode[];
  edges: GEdge[];
  summary: NetSummary;
  communities: CommunityProfile[];
  disclaimer: string;
};

export type Meta = {
  project: { id: number; code: string; name: string; period_start: string; period_end: string; is_demo: boolean };
  data_mode: "DEMO" | "LIVE";
  platforms: { code: string; name: string; color: string }[];
  categories: { code: string; name: string; color: string }[];
  layers: Record<string, string>;
  interaction_types: string[];
  evidence_statuses: { code: string; label: string; description: string }[];
  context_labels: Record<string, string>;
  metrics: Record<string, { label: string; explanation: string }>;
  disclaimer: string;
};

export type User = {
  id: number;
  username: string;
  display_name: string;
  role: string;
  role_label: string;
  permissions: string[];
  is_active: boolean;
  last_login_at: string | null;
};

export type Filters = {
  start: string;
  end: string;
  platforms: string[];
  categories: string[];
  search: string;
};
