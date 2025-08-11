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
total_strong_comm_users = 0
total_weak_comm_user = 0
total_noisy_users = 0

# Extracting weak communities
for comm_id, comm_data in tree.items():
    ctype = comm_data.get('type')
    if ctype == 'Strong community':
        total_strong_comm_users += len(comm_data.get('users', []))
    elif ctype == 'Weak community':
        total_weak_comm_user += len(comm_data.get('users', []))
    else:
        total_noisy_users += len(comm_data.get('users', []))

    if ctype in ['Weak community', 'Strong community']:
        for u in comm_data.get('users', []):
            node2comm[u] = comm_id
            node2comm_type[u] = ctype

community_map = pd.Series(node2comm, name="community_id")
community_type_map = pd.Series(node2comm_type, name="community_type")


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
df_final["external_degree"] = df_final["degree"] - df_final["internal_degree"].astype(int)

# Calculating degrees percentage
df_final["pct_internal"] = df_final["internal_degree"] / df_final["degree"]
df_final["pct_external"] = df_final["external_degree"] / df_final["degree"]

# Calculating internal community threshold
internal_thresholds = df_final.groupby("community_id")["internal_degree"].quantile(0.9)  # top 10%

df_final["is_hub"] = (
    df_final.apply(lambda row: row["internal_degree"] >= internal_thresholds.get(row["community_id"], np.inf), axis=1)
    & (df_final["pct_external"] < 0.2)
)

df_final['is_bridge'] = (
    ~df_final['is_hub'] & # A bridge user cannot be also a hub
    (df_final['pct_external'] > 0.5) &
    (df_final['community_type'].isin(['Strong community', 'Weak community'])) 
)

print(f"Total users in strong communities: {total_strong_comm_users}."
      f"\nTotal users in weak communities:{total_weak_comm_user}"
      f"\nTotal users in noisy communities: {total_noisy_users}")

print(f"\nTotal Hub users identified: {len(df_final.loc[df_final['is_hub']])}")
print(f"Total Bridge users:{len(df_final.loc[df_final['is_bridge']])}")

print(f"\nTotal hub users in strong community: {len(df_final.loc[(df_final['is_hub']) & (df_final['community_type'] == 'Strong community')])}")
print(f"Total bridge users in strong community: {len(df_final.loc[(df_final['is_bridge']) & (df_final['community_type'] == 'Strong community')])}")
print(f"Total hub users in weak community: {len(df_final.loc[(df_final['is_hub']) & (df_final['community_type'] == 'Weak community')])}")
print(f"Total bridge users in weak community: {len(df_final.loc[(df_final['is_bridge']) & (df_final['community_type'] == 'Weak community')])}")

df_final = df_final.drop(columns=['engagement', 'weighted_indegree','weighted_outdegree','weighted_degree','eccentricity','closness_centrality','harmonic_closnesscentrality','betweeness_centrality','authority','hub','pageranks','component_number','strong_comp_num','modularity_class','stat_inf_class','clustering','eigencentrality'], axis=1)
df_final.to_csv('src/data/distribuitions/hub_bridge_df.csv', sep=',', encoding='utf-8', index=False)