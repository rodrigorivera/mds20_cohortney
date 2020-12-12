# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#
import time

import faiss
from sklearn.cluster import KMeans
import numpy as np
from scipy.sparse import csr_matrix, find
import torch
import torch.utils.data as data


__all__ = ['Kmeans', 'cluster_assign', 'arrange_clustering']


class ReassignedDataset(data.Dataset):
    """A dataset where the new images labels are given in argument.
    Args:
        image_indexes (list): list of data indexes
        pseudolabels (list): list of labels for each data
        dataset (list): list of tuples with paths to images
        transform (callable, optional): a function/transform that takes in
                                        an PIL image and returns a
                                        transformed version
    """

    def __init__(self, indexes, pseudolabels, dataset, transform=None):
        self.dataset = self.make_dataset(indexes, pseudolabels, dataset)
        # self.transform = transform

    def make_dataset(self, indexes, pseudolabels, dataset):
        label_to_idx = {label: idx for idx, label in enumerate(set(pseudolabels))}
        seqs = []
        for j, idx in enumerate(indexes):
            item = dataset[idx]
            pseudolabel = label_to_idx[pseudolabels[j]]
            seqs.append((item, pseudolabel))
        return seqs

    def __getitem__(self, index):
        """
        Args:
            index (int): index of data
        Returns:
            tuple: (image, pseudolabel) where pseudolabel is the cluster of index datapoint
        """
        item, pseudolabel = self.dataset[index]

        return item, pseudolabel

    def __len__(self):
        return len(self.dataset)


def preprocess_features(npdata, pca=256):
    """Preprocess an array of features.
    Args:
        npdata (np.array N * ndim): features to preprocess
        pca (int): dim of output
    Returns:
        np.array of dim N * pca: data PCA-reduced, whitened and L2-normalized
    """
    _, ndim = npdata.shape
    npdata =  npdata.astype('float32')

    # Apply PCA-whitening with Faiss
    mat = faiss.PCAMatrix (ndim, pca, eigen_power=-0.5)
    mat.train(npdata)
    assert mat.is_trained
    npdata = mat.apply_py(npdata)

    # L2 normalization
    row_sums = np.linalg.norm(npdata, axis=1)
    npdata = npdata / row_sums[:, np.newaxis]

    return npdata


def cluster_assign(lists, dataset):
    """Creates a dataset from clustering, with clusters as labels.
    Args:
        images_lists (list of list): for each cluster, the list of image indexes
                                    belonging to this cluster
        dataset (list): initial dataset
    Returns:
        ReassignedDataset(torch.utils.data.Dataset): a dataset with clusters as
                                                     labels
    """
    assert lists is not None
    pseudolabels = []
    indexes = []
    for cluster, seqs in enumerate(lists):
        indexes.extend(seqs)
        pseudolabels.extend([cluster] * len(seqs))

    # normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
    #                                  std=[0.229, 0.224, 0.225])
    # t = transforms.Compose([transforms.RandomResizedCrop(224),
    #                         transforms.RandomHorizontalFlip(),
    #                         transforms.ToTensor(),
    #                         normalize])

    return ReassignedDataset(indexes, pseudolabels, dataset)


def run_kmeans(x, nmb_clusters, verbose=False):
    """Runs kmeans on 1 GPU.
    Args:
        x: data
        nmb_clusters (int): number of clusters
    Returns:
        list: ids of data in each cluster
    """
    n_data, d = x.shape

    # faiss implementation of k-means
    # clus = faiss.Clustering(d, nmb_clusters)

    # # Change faiss seed at each k-means so that the randomly picked
    # # initialization centroids do not correspond to the same feature ids
    # # from an epoch to another.
    # clus.seed = np.random.randint(1234)

    # clus.niter = 20
    # clus.max_points_per_centroid = 10000000
    # res = faiss.StandardGpuResources()
    # flat_config = faiss.GpuIndexFlatConfig()
    # flat_config.useFloat16 = False
    # flat_config.device = 0
    # index = faiss.GpuIndexFlatL2(res, d, flat_config)

    # # perform the training
    # clus.train(x, index)
    # _, I = index.search(x, 1)
    # losses = faiss.vector_to_array(clus.obj)
    # if verbose:
    #     print('k-means loss evolution: {0}'.format(losses))

    kmeans = KMeans(n_clusters=nmb_clusters, init='k-means++', max_iter=300, n_init=10)
    I = kmeans.fit_predict(x)

    return [int(n) for n in I], None #losses[-1]


def arrange_clustering(images_lists):
    pseudolabels = []
    image_indexes = []
    for cluster, images in enumerate(images_lists):
        image_indexes.extend(images)
        pseudolabels.extend([cluster] * len(images))
    indexes = np.argsort(image_indexes)
    return np.asarray(pseudolabels)[indexes]


class Kmeans(object):
    def __init__(self, k):
        self.k = k

    def cluster(self, data, verbose=False):
        """Performs k-means clustering.
            Args:
                x_data (np.array N * dim): data to cluster
        """
        #end = time.time()

        # PCA-reducing, whitening and L2-normalization
        #xb = preprocess_features(data)
        xb = data

        # cluster the data
        I, loss = run_kmeans(xb, self.k, verbose)
        self.lists = [[] for i in range(self.k)]
        for i in range(len(data)):
            self.lists[I[i]].append(i)

        # if verbose:
        #     print('k-means time: {0:.0f} s'.format(time.time() - end))

        return loss


