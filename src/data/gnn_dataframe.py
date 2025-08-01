import pandas as pd
import torch
from sklearn.preprocessing import MinMaxScaler
from torch_geometric.data import Data
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)

# Caricamento dati
nodes = pd.read_csv('src/data/statistical_nodes.csv')
edges = pd.read_csv('src/data/edges.csv')

# Mappatura ID utente → indice numerico
user2idx = {uid: idx for idx, uid in enumerate(nodes['id'])}
idx2user = {idx: uid for uid, idx in user2idx.items()}

# Controllo di consistenza
assert set(edges['source']).issubset(user2idx), "Some edge sources not in node list"
assert set(edges['target']).issubset(user2idx), "Some edge targets not in node list"

# Ordinamento nodi coerente con user2idx
ordered_ids = list(user2idx.keys())
nodes = nodes.set_index('id').loc[ordered_ids].reset_index()

# Scaling features dei nodi
features_to_scale = ['engagement','indegree','outdegree','degree','eccentricity','authority'] 
node_scaler = MinMaxScaler()
nodes[features_to_scale] = node_scaler.fit_transform(nodes[features_to_scale])
nodes_features = torch.tensor(nodes[features_to_scale].values, dtype=torch.float)

# Scaling pesi degli archi
edge_scaler = MinMaxScaler()
edges['weight'] = edge_scaler.fit_transform(edges[['weight']])

# Creazione edge_index e edge_weight
edges_index = torch.tensor([
    [user2idx[src] for src in edges['source']],\
    [user2idx[dst] for dst in edges['target']],
], dtype=torch.long)

edges_weight = torch.tensor(edges['weight'].values, dtype=torch.float)

# Define iterable edges structure
src_list = edges_index[0].tolist()
trg_list = edges_index[1].tolist()
w_list = edges_weight.tolist()

# Aggregates symmetric edges
edge_dict = defaultdict(int)
for u,v, w in zip(src_list, trg_list, w_list):
    key = tuple(sorted((u,v))) # In non-directed -> (min(u,v), max(u,v))
    edge_dict[key] += w

# Building nre edge_index and edge_weight
new_edges = list(edge_dict.keys())
new_weights = list(edge_dict.values())

edges_index = torch.tensor(new_edges, dtype=torch.long).t()
edges_weight = torch.tensor(new_weights, dtype=torch.int)

# Creazione del grafo
data = Data(x=nodes_features, edge_index=edges_index, edge_weight=edges_weight)
torch.save({
    'data': data,
    'idx2user': idx2user,
}, 'src/data/graph_data.pt')

logging.info(f"Graph saved: {data.num_nodes} nodes, {data.num_edges} edges.")
