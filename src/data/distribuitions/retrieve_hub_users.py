import sqlite3
import pandas as pd
import numpy as np
import json

nodes = pd.read_csv('src/data/statistical_nodes.csv')
edges = pd.read_csv('src/data/edges.csv')

# Calculating external and internal degree
with open('src/graph_dir/infomap_dir/cluster_tree_base.json', 'r') as f:
    tree = json.load(f)

node2comm = {}
node2comm_type = {}

total_very_strong_users = 0
total_strong_users = 0
total_moderate_users = 0
total_weak_users = 0

# Extracting weak communities
for comm_id, comm_data in tree.items():
    ctype = comm_data.get('type')
    num_users = len(comm_data.get('users', []))
    
    if ctype == 'Very Strong community':
        total_very_strong_users += num_users
    elif ctype == 'Strong community':
        total_strong_users += num_users
    elif ctype == 'Moderate community':
        total_moderate_users += num_users
    elif ctype == 'Weak community':
        total_weak_users += num_users

    for u in comm_data.get('users', []):
        node2comm[u] = comm_id
        node2comm_type[u] = ctype

community_map = pd.Series(node2comm, name="community_id")
community_type_map = pd.Series(node2comm_type, name="community_type")

valid_comm_types = ['Very Strong community', 'Strong community', 'Moderate community', 'Weak community']

# Labeling each edge node with its community and then filtering edges of the same community 
edges['src_comm'] = edges['source'].map(community_map)
edges['dst_comm'] = edges['target'].map(community_map)

edges_internal = edges[(edges["src_comm"] == edges["dst_comm"]) & edges["src_comm"].notna()]

endpoints = pd.concat([edges_internal["source"], edges_internal["target"]])
internal_deg = endpoints.value_counts().rename("internal_degree")

# Associate each node to its degree
df_deg = internal_deg.to_frame().join(community_map)

# Computing external degree: degree - internal degree
df_final = nodes.merge(df_deg, left_on='id', right_index=True, how='left')
df_final = df_final.join(community_type_map, on='id')

df_final["internal_degree"] = df_final["internal_degree"].fillna(0).astype(int)
df_final["external_degree"] = (df_final["degree"] - df_final["internal_degree"].astype(int)).abs()

# Calculating degrees percentage
df_final["pct_internal"] = df_final["internal_degree"] / df_final["degree"]
df_final["pct_external"] = df_final["external_degree"] / df_final["degree"]

# Calculating internal community threshold
internal_degree_threshold = df_final.groupby("community_id")["internal_degree"].transform(
    lambda x: max(x.quantile(0.9), 5) 
)

df_final["is_hub"] = (
    (df_final["internal_degree"] >= internal_degree_threshold) &
    (df_final["pct_external"] < 0.2) &
    (df_final['community_type'].isin(valid_comm_types))
)

# Defining adaptive threshold to defining bridge users
pct_external_threshold = df_final['pct_external'].quantile(0.75)  # 75° percentile
external_degree_threshold = df_final['external_degree'].quantile(0.5)  # Median

df_final['is_bridge'] = (
    ~df_final['is_hub'] &
    (df_final['pct_external'] > pct_external_threshold) &
    (df_final['external_degree'] > external_degree_threshold) &
    (df_final['community_type'].isin(valid_comm_types))
)

print(f"Total users in very strong communities: {total_very_strong_users}")
print(f"Total users in strong communities: {total_strong_users}")
print(f"Total users in moderate communities: {total_moderate_users}")
print(f"Total users in weak communities: {total_weak_users}")

print(f"\nTotal Hub users identified: {len(df_final.loc[df_final['is_hub']])}")
print(f"Total Bridge users:{len(df_final.loc[df_final['is_bridge']])}")

for ctype in valid_comm_types:
    print(f"Total hub users in {ctype}: {len(df_final.loc[(df_final['is_hub']) & (df_final['community_type'] == ctype)])}")
    print(f"Total bridge users in {ctype}: {len(df_final.loc[(df_final['is_bridge']) & (df_final['community_type'] == ctype)])}")

df_final = df_final.drop(columns=['engagement','weighted_degree','eccentricity','closeness_centrality','harmonic_closeness_centrality','betweenness_centrality','authority','hub','pagerank'], axis=1)
df_final.to_csv('src/data/distribuitions/hub_bridge_df.csv', sep=',', encoding='utf-8', index=False)