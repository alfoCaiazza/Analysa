import pandas as pd
import torch

nodes = pd.read_csv('src/data/nodes.csv')
edges = pd.read_csv('src/data/edges.csv')

user2idx = {uid: idx for idx, uid in enumerate(nodes['user_name'])}

edge_index = torch.tensor([
    [user2idx[src] for src in edges['src']],
    [user2idx[dst] for dst in edges['dst']],
], dtype=torch.long)

edge_weight = torch.tensor(edges['weight'].values, dtype=torch.float)