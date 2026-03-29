import os
from dataclasses import dataclass
from glob import glob
from os.path import join

import numpy as np
import pydicom
from numpy import ndarray
from pydicom.dataset import FileDataset


@dataclass
class Sample:
    ct: ndarray | None
    seg: ndarray | None
    sr: FileDataset | None


def read_sample(sample_path: str) -> Sample:
    ct: ndarray | None = None
    seg: ndarray | None = None
    sr: FileDataset | None = None

    for series_dir in glob(join(sample_path, '*')):
        if not os.path.isdir(series_dir):
            continue
        for dcm_path in glob(join(series_dir, '*.dcm')):
            ds = pydicom.dcmread(dcm_path, stop_before_pixels=True, force=True)
            modality = ds.Modality
            break
        else:
            continue

        if modality == 'CT' and ct is None:
            ct = _read_ct(series_dir)
        elif modality == 'SEG':
            seg_mask = pydicom.dcmread(join(series_dir, '1-1.dcm')).pixel_array
            if seg is None:
                seg = seg_mask
            elif seg.shape[0] == seg_mask.shape[0]:
                seg = np.maximum(seg, seg_mask)
            else:
                # 不同 SEG 帧数不同，pad 到较大尺寸后再合并
                max_slices = max(seg.shape[0], seg_mask.shape[0])
                padded = np.zeros((max_slices, seg.shape[1], seg.shape[2]), dtype=seg.dtype)
                padded[:seg.shape[0]] = seg
                padded_mask = np.zeros_like(padded)
                padded_mask[:seg_mask.shape[0]] = seg_mask
                seg = np.maximum(padded, padded_mask)
        elif modality == 'SR' and sr is None:
            sr = pydicom.dcmread(join(series_dir, '1-1.dcm'))

    return Sample(ct=ct, seg=seg, sr=sr)


def _read_ct(series_dir: str) -> ndarray:
    slices = sorted(glob(join(series_dir, '*.dcm')))
    datasets = [pydicom.dcmread(f) for f in slices if not f.endswith('LICENSE.dcm')]
    datasets.sort(key=lambda d: float(d.ImagePositionPatient[2]))
    return np.stack([d.pixel_array for d in datasets])