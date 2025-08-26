import pandas as pd
import numpy as np
import networkx as nx
import json
import igraph as ig

nodes = pd.read_csv('src/data/statistical_nodes.csv')
edges = pd.read_csv('src/data/edges.csv')
G_nx = nx.from_pandas_edgelist(edges, source="source", target="target")

# Mapping node to id
node_list = list(G_nx.nodes())
node2idx = {node: idx for idx, node in enumerate(node_list)}

# Calculating external and internal degree
with open('src/graph_dir/infomap_dir/cluster_tree_base.json', 'r') as f:
    tree = json.load(f)

node2comm = {}
node2comm_type = {}

for comm_id, comm_data in tree.items():
    ctype = comm_data.get('type')
    for u in comm_data.get('users', []):
        node2comm[u] = comm_id
        node2comm_type[u] = ctype

community_map = pd.Series(node2comm, name="community_id")
community_type_map = pd.Series(node2comm_type, name="community_type")

# Labeling each edge node with its community and then filtering edges of the same community 
edges['src_comm'] = edges['source'].map(community_map)
edges['dst_comm'] = edges['target'].map(community_map)

# Internal degree
edges_internal = edges[(edges["src_comm"] == edges["dst_comm"]) & edges["src_comm"].notna()]
endpoints = pd.concat([edges_internal["source"], edges_internal["target"]])
internal_deg = endpoints.value_counts().rename("internal_degree")

df_deg = internal_deg.to_frame().join(community_map)

# Merge with nodes
df_final = nodes.merge(df_deg, left_on='id', right_index=True, how='left')
df_final = df_final.join(community_type_map, on='id')

df_final["internal_degree"] = df_final["internal_degree"].fillna(0).astype(int)
df_final["external_degree"] = (df_final["degree"] - df_final["internal_degree"].astype(int)).clip(lower=0)

# Computing degrees percentage
df_final["pct_internal"] = df_final["internal_degree"] / df_final["degree"].replace(0, np.nan)
df_final["pct_external"] = df_final["external_degree"] / df_final["degree"].replace(0, np.nan)

# Scaling
df_final["z_internal"] = df_final.groupby("community_id")["internal_degree"].transform(
    lambda x: (x - x.mean()) / (x.std() + 1e-9)
)

# Computing betweeness intra-community and centrality
df_final["z_internal"] = df_final.groupby("community_id")["internal_degree"].transform(
    lambda x: (x - x.mean()) / (x.std() + 1e-9)
)

g = ig.Graph.TupleList(G_nx.edges(), directed=False)
betw = g.betweenness()
betw_dict = {node: betw[idx] for node, idx in node2idx.items()}
df_final["betweenness"] = df_final["id"].map(betw_dict)

# Defining adaptive thresholds
internal_degree_threshold = df_final.groupby("community_id")["internal_degree"].transform(
    lambda x: np.percentile(x, 90) if len(x) > 10 else max(x)
)

pct_external_threshold = df_final['pct_external'].quantile(0.75)
external_degree_threshold = df_final['external_degree'].median()
betweenness_threshold = df_final["betweenness"].quantile(0.75)

# Hub and Bridge classification
df_final["is_hub"] = (
    (df_final["z_internal"] > 2) &  # molto sopra la media della community
    (df_final["internal_degree"] >= internal_degree_threshold) &
    (df_final["pct_external"] < 0.2)
)

df_final["is_bridge"] = (
    ~df_final['is_hub'] &
    (df_final["pct_external"] > pct_external_threshold) &
    (df_final["external_degree"] > external_degree_threshold) &
    (df_final["betweenness"] > betweenness_threshold)
)

# --- Salvataggio ---
df_final = df_final.drop(
    columns=['engagement','weighted_degree','eccentricity','closeness_centrality',
             'harmonic_closeness_centrality','betweenness_centrality',
             'authority','hub','pagerank'], errors="ignore"
)

df_final.to_csv('src/data/distribuitions/hub_bridge_df.csv', sep=',', encoding='utf-8', index=False)

# Report
print(f"Totale Hub: {df_final['is_hub'].sum()}")
print(f"Totale Bridge: {df_final['is_bridge'].sum()}")
print(df_final.groupby("community_type")[["is_hub","is_bridge"]].sum())