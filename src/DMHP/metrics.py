import torch
import numpy as np


def consistency(trials_labels):
    J = len(trials_labels)
    values = torch.zeros(J)
    
    for trial_id, labels in enumerate(trials_labels):
        for trial_id2, labels2 in enumerate(trials_labels):
            if trial_id == trial_id2:
                continue
            ks = torch.unique(labels)
            sz_M = 0
            for k in ks:
                mask = labels == k
                sz = mask.sum()
                s = sz * (sz - 1.) / 2.
                sz_M += s

            for k in ks:
                mask = labels == k
                s2 = 0
                for k2 in labels2[mask].unique():
                    sz = (labels2[mask] == k2).sum()
                    s2 += sz * (sz - 1.) / 2.
                values[trial_id] += (s - s2) / ((J-1) * sz_M)
    
    return torch.min(values)


def purity(learned_ids, gt_ids):
    assert len(learned_ids) == len(gt_ids)
    pur = 0
    ks = torch.unique(learned_ids)
    js = torch.unique(gt_ids)
    for k in ks:
        inters = []
        for j in js:
            inters.append(((learned_ids == k) * (gt_ids == j)).sum().item())
        pur += 1./len(learned_ids) * max(inters)

    return pur
