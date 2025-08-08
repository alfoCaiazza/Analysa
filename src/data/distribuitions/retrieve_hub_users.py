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

df_final["internal_degree"] = df_final["internal_degree"].fillna(0)
df_final["external_degree"] = df_final["degree"] - df_final["internal_degree"]

hub_users = df_final[
    (df_final['community_id'].notna()) &
    (df_final['internal_degree'] > df_final['external_degree'])
]

hub_users['bridge_value'] = hub_users['external_degree'].div(hub_users['degree'])

print(f"Total users in strong communities: {total_strong_comm_users}."
      f"\nTotal users in weak communities:{total_weak_comm_user}"
      f"\nTotal users in noisy communities: {total_noisy_users}")
print(f"Total hub users identified: {len(hub_users)}")
print(f"Hub users:\n{hub_users[['id', 'community_id', 'community_type', 'bridge_value']]}")
print(f"Max bridge value: {hub_users['bridge_value'].max()}")
print(f"total Hub-Bridge users:{len(hub_users.loc[hub_users['bridge_value'] > 0.3])}")
print(f"Hub-Bridge users:\n{hub_users.loc[hub_users['bridge_value'] > 0.3, ['id', 'community_id', 'community_type', 'bridge_value']]}")

print(f"\nTotal hub users in strong community: {len(hub_users.loc[hub_users['community_type'] == 'Strong community'])}")
print(f"\nTotal bridge users in strong community: {len(hub_users.loc[(hub_users['bridge_value'] > 0.3) & (hub_users['community_type'] == 'Strong community')])}")
print(f"\nTotal hub users in weak community: {len(hub_users.loc[hub_users['community_type'] == 'Weak community'])}")
print(f"\nTotal bridge users in weak community: {len(hub_users.loc[(hub_users['bridge_value'] > 0.3) & (hub_users['community_type'] == 'Weak community')])}")
