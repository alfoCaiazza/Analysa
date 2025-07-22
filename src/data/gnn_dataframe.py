import pandas as pd
import torch
from sklearn.preprocessing import MinMaxScaler
from torch_geometric.data import Data
import logging

logging.basicConfig(level=logging.INFO,)

nodes = pd.read_csv('src/data/nodes.csv')
edges = pd.read_csv('src/data/edges.csv')

# Creating dictionary author - numerical id
user2idx = {uid: idx for idx, uid in enumerate(nodes['user_name'])}
idx2user = {idx: username for username, idx in user2idx.items()}
nodes = nodes.set_index('user_name').loc[user2idx.keys()].reset_index()

# Scaling nodes engagement
node_scaler = MinMaxScaler()
nodes['engagement'] = node_scaler.fit_transform(nodes['engagement'].values.reshape(-1,1))
node_features = torch.tensor(nodes['engagement'].values, dtype=torch.float).unsqueeze(1)

# Scaling edges weights
edge_scaler = MinMaxScaler()
edges['weight'] = edge_scaler.fit_transform(edges['weight'].values.reshape(-1,1))

# Making the graph not-oriented
edges_undirected = pd.concat([edges, edges.rename(columns={'src':'dst', 'dst':'src'})])
edges_index = torch.tensor([
    [user2idx[src] for src in edges_undirected['src']],
    [user2idx[dst] for dst in edges_undirected['dst']],
], dtype=torch.long)

edges_weight = torch.tensor(edges_undirected['weight'].values, dtype=torch.float)

# Creating and saving Data instance for the GNN models
data = Data(x=node_features, edge_index=edges_index, edge_weight=edges_weight)
torch.save({
    'data': data,
    'idx2user': idx2user,
}, 'src/data/graph_data.pt')

logging.info(f"Graph saved: {data.num_nodes} nodes, {data.num_edges} edges.")