# from torch_geometric.datasets import TUDataset
import os.path as osp
import torch

import torch
from torch_geometric.data import InMemoryDataset, download_url, extract_zip
from torch.utils.data import Dataset, DataLoader
from torch_geometric.utils import degree
from torch_geometric.io import read_tu_data
import torch
from typing import Optional, Callable, List
from itertools import repeat, product
import torch.nn.functional as F
import numpy as np
import os
import shutil


class TUDataset(InMemoryDataset):
    r"""A variety of graph kernel benchmark datasets, *.e.g.* "IMDB-BINARY",
    "REDDIT-BINARY" or "PROTEINS", collected from the `TU Dortmund University
    <https://chrsmrrs.github.io/datasets>`_.
    In addition, this dataset wrapper provides `cleaned dataset versions
    <https://github.com/nd7141/graph_datasets>`_ as motivated by the
    `"Understanding Isomorphism Bias in Graph Data Sets"
    <https://arxiv.org/abs/1910.12091>`_ paper, containing only non-isomorphic
    graphs.

    .. note::
        Some datasets may not come with any node labels.
        You can then either make use of the argument :obj:`use_node_attr`
        to load additional continuous node attributes (if present) or provide
        synthetic node features using transforms such as
        like :class:`torch_geometric.transforms.Constant` or
        :class:`torch_geometric.transforms.OneHotDegree`.

    Args:
        root (string): Root directory where the dataset should be saved.
        name (string): The `name
            <https://chrsmrrs.github.io/datasets/docs/datasets/>`_ of the
            dataset.
        transform (callable, optional): A function/transform that takes in an
            :obj:`torch_geometric.data.Data` object and returns a transformed
            version. The data object will be transformed before every access.
            (default: :obj:`None`)
        pre_transform (callable, optional): A function/transform that takes in
            an :obj:`torch_geometric.data.Data` object and returns a
            transformed version. The data object will be transformed before
            being saved to disk. (default: :obj:`None`)
        pre_filter (callable, optional): A function that takes in an
            :obj:`torch_geometric.data.Data` object and returns a boolean
            value, indicating whether the data object should be included in the
            final dataset. (default: :obj:`None`)
        use_node_attr (bool, optional): If :obj:`True`, the dataset will
            contain additional continuous node attributes (if present).
            (default: :obj:`False`)
        use_edge_attr (bool, optional): If :obj:`True`, the dataset will
            contain additional continuous edge attributes (if present).
            (default: :obj:`False`)
        cleaned: (bool, optional): If :obj:`True`, the dataset will
            contain only non-isomorphic graphs. (default: :obj:`False`)
    """

    url = 'https://www.chrsmrrs.com/graphkerneldatasets'
    cleaned_url = ('https://raw.githubusercontent.com/nd7141/'
                   'graph_datasets/master/datasets')

    def __init__(self, root: str, name: str,
                 transform: Optional[Callable] = None,
                 pre_transform: Optional[Callable] = None,
                 pre_filter: Optional[Callable] = None,
                 use_node_attr: bool = False, use_edge_attr: bool = False,
                 cleaned: bool = False):
        self.name = name
        self.cleaned = cleaned
        super().__init__(root, transform, pre_transform, pre_filter)
        self.data, self.slices = torch.load(self.processed_paths[0])
        if self.data.x is not None and not use_node_attr:
            num_node_attributes = self.num_node_attributes
            self.data.x = self.data.x[:, num_node_attributes:]
        if self.data.edge_attr is not None and not use_edge_attr:
            num_edge_attributes = self.num_edge_attributes
            self.data.edge_attr = self.data.edge_attr[:, num_edge_attributes:]

        if not (self.name == 'MUTAG' or self.name == 'PTC_MR' or self.name == 'DD' or self.name == 'PROTEINS' or self.name == 'NCI1' or self.name == 'NCI109' or self.name == 'Mutagenicity'):
            edge_index = self.data.edge_index[0, :].numpy()
            _, num_edge = self.data.edge_index.size()
            nlist = [edge_index[n] + 1 for n in range(num_edge - 1) if edge_index[n] > edge_index[n + 1]]
            nlist.append(edge_index[-1] + 1)

            num_node = np.array(nlist).sum()
            self.data.x = torch.ones((num_node, 1))

            # deg = degree(self.data.edge_index[0], num_node, dtype = torch.long)
            # self.data.x = F.one_hot(deg).type(torch.float)

            edge_slice = [0]
            k = 0
            for n in nlist:
                k = k + n
                edge_slice.append(k)
            self.slices['x'] = torch.tensor(edge_slice)

        self.data.id = torch.arange(0, self.data.y.size(0))
        self.slices['id'] = self.slices['y'].clone()

    @property
    def raw_dir(self) -> str:
        name = f'raw{"_cleaned" if self.cleaned else ""}'
        return osp.join(self.root, self.name, name)

    @property
    def processed_dir(self) -> str:
        name = f'processed{"_cleaned" if self.cleaned else ""}'
        return osp.join(self.root, self.name, name)

    @property
    def num_node_labels(self) -> int:
        if self.data.x is None:
            return 0
        for i in range(self.data.x.size(1)):
            x = self.data.x[:, i:]
            if ((x == 0) | (x == 1)).all() and (x.sum(dim=1) == 1).all():
                return self.data.x.size(1) - i
        return 0

    @property
    def num_node_attributes(self) -> int:
        if self.data.x is None:
            return 0
        return self.data.x.size(1) - self.num_node_labels

    @property
    def num_edge_labels(self) -> int:
        if self.data.edge_attr is None:
            return 0
        for i in range(self.data.edge_attr.size(1)):
            if self.data.edge_attr[:, i:].sum() == self.data.edge_attr.size(0):
                return self.data.edge_attr.size(1) - i
        return 0

    @property
    def num_edge_attributes(self) -> int:
        if self.data.edge_attr is None:
            return 0
        return self.data.edge_attr.size(1) - self.num_edge_labels

    @property
    def raw_file_names(self) -> List[str]:
        names = ['A', 'graph_indicator']
        return [f'{self.name}_{name}.txt' for name in names]

    @property
    def processed_file_names(self) -> str:
        return 'data.pt'

    def download(self):
        url = self.cleaned_url if self.cleaned else self.url
        folder = osp.join(self.root, self.name)
        path = download_url(f'{url}/{self.name}.zip', folder)
        extract_zip(path, folder)
        os.unlink(path)
        shutil.rmtree(self.raw_dir)
        os.rename(osp.join(folder, self.name), self.raw_dir)

    def process(self):
        self.data, self.slices = read_tu_data(self.raw_dir, self.name)

        if self.pre_filter is not None:
            data_list = [self.get(idx) for idx in range(len(self))]
            data_list = [data for data in data_list if self.pre_filter(data)]
            self.data, self.slices = self.collate(data_list)

        if self.pre_transform is not None:
            data_list = [self.get(idx) for idx in range(len(self))]
            data_list = [self.pre_transform(data) for data in data_list]
            self.data, self.slices = self.collate(data_list)

        torch.save((self.data, self.slices), self.processed_paths[0])

    def __repr__(self) -> str:
        return f'{self.name}({len(self)})'

    # def get_num_feature(self):
    #     data = self.data.__class__()

    #     if hasattr(self.data, '__num_nodes__'):
    #         data.num_nodes = self.data.__num_nodes__[0]

    #     for key in self.data.keys:
    #         item, slices = self.data[key], self.slices[key]
    #         if torch.is_tensor(item):
    #             s = list(repeat(slice(None), item.dim()))
    #             s[self.data.__cat_dim__(key,
    #                                     item)] = slice(slices[0],
    #                                                    slices[0 + 1])
    #         else:
    #             s = slice(slices[idx], slices[idx + 1])
    #         data[key] = item[s]
    #     _, num_feature = data.x.size()

    #     return num_feature


    # def get(self, idx):
    #     data = self.data.__class__()

    #     if hasattr(self.data, '__num_nodes__'):
    #         data.num_nodes = self.data.__num_nodes__[idx]

    #     for key in self.data.keys:
    #         item, slices = self.data[key], self.slices[key]
    #         if torch.is_tensor(item):
    #             s = list(repeat(slice(None), item.dim()))
    #             s[self.data.__cat_dim__(key,
    #                                     item)] = slice(slices[idx],
    #                                                    slices[idx + 1])
    #         else:
    #             s = slice(slices[idx], slices[idx + 1])
    #         data[key] = item[s]

    #     return data


def get_TUDataset(dataset):
    """
    'PROTEINS', 'REDDIT-BINARY', 'IMDB-BINARY', 'MUTAG', 'PTC_MR', 'DD', 'NCI1', 'NCI109'
    """
    path = osp.join(osp.dirname(osp.realpath(__file__)), '..', 'data', 'TU')
    dataset = TUDataset(path, name=dataset).shuffle()

    n_feat, n_class = max(dataset.num_features, 1), dataset.num_classes

    mapping = {}
    for i in range(len(dataset)):
        mapping[dataset[i].id.item()] = i

    return dataset, n_feat, n_class, mapping


def shuffle(dataname, dataset, imb_ratio, num_train, num_val):
    class_train_num_graph = [
        int(imb_ratio * num_train), num_train - int(imb_ratio * num_train)]
    class_val_num_graph = [int(imb_ratio * num_val),
                           num_val - int(imb_ratio * num_val)]

    y = torch.tensor([data.y.item() for data in dataset])

    classes = torch.unique(y)

    indices = []
    for i in range(len(classes)):
        index = torch.nonzero(y == classes[i]).view(-1)
        index = index[torch.randperm(index.size(0))]
        indices.append(index)

    train_index, val_index, test_index = [], [], []
    for i in range(len(classes)):
        train_index.append(indices[classes[i]]
                           [:class_train_num_graph[classes[i]]])
        val_index.append(indices[classes[i]]
                         [class_train_num_graph[classes[i]]:(class_train_num_graph[classes[i]] + class_val_num_graph[classes[i]])])
        test_index.append(indices[classes[i]]
                          [(class_train_num_graph[classes[i]] + class_val_num_graph[classes[i]]):])

    train_index = torch.cat(train_index, dim=0)
    val_index = torch.cat(val_index, dim=0)
    test_index = torch.cat(test_index, dim=0)

    train_dataset = dataset[train_index]
    val_dataset = dataset[val_index]
    test_dataset = dataset[test_index]

    return train_dataset, val_dataset, test_dataset, torch.tensor(class_train_num_graph), torch.tensor(class_val_num_graph)
