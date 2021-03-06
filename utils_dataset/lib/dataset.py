from abc import ABC
from pathlib import Path
from collections import defaultdict

import random
import numpy as np
from enum import Enum

import torch
from torch.utils.data import Dataset, DataLoader

import MinkowskiEngine as ME

from obj_geo_utils.line_operations import m_transform_bboxes

from plyfile import PlyData
from . import transforms as t
from .dataloader import InfSampler
from .voxelizer import Voxelizer
from tools.debug_utils import _show_3d_points_bboxes_ls, _show_lines_ls_points_ls
from tools.visual_utils import _show_3d_points_objs_ls
from configs.common import DEBUG_CFG

DEBUG = 0

class DatasetPhase(Enum):
  Train = 0
  Val = 1
  Val2 = 2
  TrainVal = 3
  Test = 4


def datasetphase_2str(arg):
  if arg == DatasetPhase.Train:
    return 'train'
  elif arg == DatasetPhase.Val:
    return 'val'
  elif arg == DatasetPhase.Val2:
    return 'val2'
  elif arg == DatasetPhase.TrainVal:
    return 'trainval'
  elif arg == DatasetPhase.Test:
    return 'test'
  else:
    raise ValueError('phase must be one of dataset enum.')


def str2datasetphase_type(arg):
  if arg.upper() == 'TRAIN':
    return DatasetPhase.Train
  elif arg.upper() == 'VAL':
    return DatasetPhase.Val
  elif arg.upper() == 'VAL2':
    return DatasetPhase.Val2
  elif arg.upper() == 'TRAINVAL':
    return DatasetPhase.TrainVal
  elif arg.upper() == 'TEST':
    return DatasetPhase.Test
  else:
    raise ValueError('phase must be one of train/val/test')


def cache(func):

  def wrapper(self, *args, **kwargs):
    # Assume that args[0] is index
    index = args[0]
    if self.cache:
      if index not in self.cache_dict[func.__name__]:
        results = func(self, *args, **kwargs)
        self.cache_dict[func.__name__][index] = results
      return self.cache_dict[func.__name__][index]
    else:
      return func(self, *args, **kwargs)

  return wrapper


class DictDataset(Dataset, ABC):

  IS_FULL_POINTCLOUD_EVAL = False

  def __init__(self,
               data_paths,
               prevoxel_transform=None,
               input_transform=None,
               target_transform=None,
               cache=False,
               data_root='/'):
    """
    data_paths: list of lists, [[str_path_to_input, str_path_to_label], [...]]
    """
    Dataset.__init__(self)

    # Allows easier path concatenation
    if not isinstance(data_root, Path):
      data_root = Path(data_root)

    self.data_root = data_root
    self.data_paths = sorted(data_paths)

    self.prevoxel_transform = prevoxel_transform
    self.input_transform = input_transform
    self.target_transform = target_transform

    # dictionary of input
    self.data_loader_dict = {
        'input': (self.load_input, self.input_transform),
        'target': (self.load_target, self.target_transform)
    }

    # For large dataset, do not cache
    self.cache = cache
    self.cache_dict = defaultdict(dict)
    self.loading_key_order = ['input', 'target']

  def load_input(self, index):
    raise NotImplementedError

  def load_target(self, index):
    raise NotImplementedError

  def get_classnames(self):
    pass

  def reorder_result(self, result):
    return result

  def __getitem__(self, index):
    out_array = []
    for k in self.loading_key_order:
      loader, transformer = self.data_loader_dict[k]
      v = loader(index)
      if transformer:
        v = transformer(v)
      out_array.append(v)
    return out_array

  def __len__(self):
    return len(self.data_paths)


class VoxelizationDatasetBase(DictDataset, ABC):
  IS_TEMPORAL = False
  CLIP_BOUND = (-1000, -1000, -1000, 1000, 1000, 1000)
  ROTATION_AXIS = None
  NUM_IN_CHANNEL = None
  NUM_LABELS = -1  # Number of labels in the dataset, including all ignore classes
  IGNORE_LABELS = None  # labels that are not evaluated

  def __init__(self,
               data_paths,
               prevoxel_transform=None,
               input_transform=None,
               target_transform=None,
               cache=False,
               data_root='/',
               ignore_mask=255,
               return_transformation=False,
               **kwargs):
    """
    ignore_mask: label value for ignore class. It will not be used as a class in the loss or evaluation.
    """
    DictDataset.__init__(
        self,
        data_paths,
        prevoxel_transform=prevoxel_transform,
        input_transform=input_transform,
        target_transform=target_transform,
        cache=cache,
        data_root=data_root)

    self.ignore_mask = ignore_mask
    self.return_transformation = return_transformation

  def __getitem__(self, index):
    raise NotImplementedError

  def load_ply(self, index):
    raise NotImplementedError

  def __len__(self):
    num_data = len(self.data_paths)
    return num_data


class VoxelizationDataset(VoxelizationDatasetBase):
  """This dataset loads RGB point clouds and their labels as a list of points
  and voxelizes the pointcloud with sufficient data augmentation.
  """
  # Voxelization arguments
  VOXEL_SIZE = None  # 5cm

  # Coordinate Augmentation Arguments: Unlike feature augmentation, coordinate
  # augmentation has to be done before voxelization
  SCALE_AUGMENTATION_BOUND = (0.9, 1.1)
  ROTATION_AUGMENTATION_BOUND = ((-np.pi / 6, np.pi / 6), (-np.pi, np.pi), (-np.pi / 6, np.pi / 6))
  TRANSLATION_AUGMENTATION_RATIO_BOUND = ((-0.2, 0.2), (-0.05, 0.05), (-0.2, 0.2))
  ELASTIC_DISTORT_PARAMS = None

  # MISC.
  PREVOXELIZATION_VOXEL_SIZE = None

  # Augment coords to feats
  AUGMENT_COORDS_TO_FEATS = False
  NORMALIZATION = False

  def __init__(self,
               data_paths,
               prevoxel_transform=None,
               input_transform=None,
               target_transform=None,
               data_root='/',
               ignore_label=255,
               return_transformation=False,
               augment_data=False,
               config=None,
               **kwargs):

    self.augment_data = augment_data
    self.config = config
    VoxelizationDatasetBase.__init__(
        self,
        data_paths,
        prevoxel_transform=prevoxel_transform,
        input_transform=input_transform,
        target_transform=target_transform,
        cache=cache,
        data_root=data_root,
        ignore_mask=ignore_label,
        return_transformation=return_transformation)

    # Prevoxel transformations
    self.voxelizer = Voxelizer(
        voxel_size=self.VOXEL_SIZE,
        clip_bound=self.CLIP_BOUND,
        use_augmentation=augment_data,
        scale_augmentation_bound=self.SCALE_AUGMENTATION_BOUND,
        rotation_augmentation_bound=self.ROTATION_AUGMENTATION_BOUND,
        translation_augmentation_ratio_bound=self.TRANSLATION_AUGMENTATION_RATIO_BOUND,
        ignore_label=ignore_label,
        max_voxel_footprint = self.max_voxel_footprint,)

    # map labels not evaluated to ignore_label
    label_map = {}
    n_used = 0
    for l in range(self.NUM_LABELS):
      if self.IGNORE_LABELS is not None and l in self.IGNORE_LABELS:
        label_map[l] = self.ignore_mask
      else:
        label_map[l] = n_used
        n_used += 1
    label_map[self.ignore_mask] = self.ignore_mask
    self.label_map = label_map
    if self.IGNORE_LABELS is not None:
      self.NUM_LABELS -= len(self.IGNORE_LABELS)

  def _augment_coords_to_feats(self, coords, feats, labels=None):
    norm_coords = coords - coords.mean(0)
    # color must come first.
    if isinstance(coords, np.ndarray):
      feats = np.concatenate((feats, norm_coords), 1)
    else:
      feats = torch.cat((feats, norm_coords), 1)
    return coords, feats, labels

  def convert_mat2cfl(self, mat):
    # Generally, xyz,rgb,label
    return mat[:, :3], mat[:, 3:-1], mat[:, -1]

  def __getitem__(self, index):
    if self.load_voxlized_sparse != False:
      return self.load_sparse_input(index, self.load_voxlized_sparse=='aug')

    debug = 0

    img_info = self.img_infos[index].copy()

    is_include_gt_bboxes = 'gt_bboxes_2d_raw' in img_info
    if is_include_gt_bboxes:
      gt_bboxes = img_info['gt_bboxes_2d_raw']
    else:
      gt_bboxes = None
    img_meta = img_info['img_meta']

    coords, feats, labels, center = self.load_ply(index)
    # Downsample the pointcloud with finer voxel size before transformation for memory and speed
    if self.PREVOXELIZATION_VOXEL_SIZE is not None:
      inds = ME.utils.sparse_quantize(
          coords / self.PREVOXELIZATION_VOXEL_SIZE, return_index=True)
      coords = coords[inds]
      feats = feats[inds]
      labels = labels[inds]

    # Prevoxel transformations
    if self.prevoxel_transform is not None:
      coords, feats, labels = self.prevoxel_transform(coords, feats, labels)

    if DEBUG_CFG.VISUAL_SPARSE_3D_TRANSFORM and 0:
      scale = 1
      print('\n\ncoords min:', coords.min(0))
      print('coords max:', coords.max(0))
      print('gt min    :', gt_bboxes[:,:4].reshape(-1,2).min(0))
      print('gt max    :', gt_bboxes[:,:4].reshape(-1,2).max(0))
      _show_3d_points_objs_ls([coords], objs_ls=[gt_bboxes], obj_rep=self.obj_rep)

    #coords_raw = coords.copy()
    coords, feats, labels, transformation, rotate_angles, scale_rate = self.voxelizer.voxelize(
        coords, feats, labels, center=center)

    #un_voxelization_matrix = np.eye(4)
    #np.fill_diagonal(un_voxelization_matrix[:3, :3], self.VOXEL_SIZE)
    #line_transformation = transformation @ un_voxelization_matrix
    line_transformation = transformation
    img_meta['data_aug']['transformation'] = transformation
    img_meta['data_aug']['rotate_angles'] = rotate_angles
    img_meta['data_aug']['scale_rate'] = scale_rate
    if is_include_gt_bboxes:
      gt_bboxes = m_transform_bboxes(gt_bboxes, line_transformation, self.obj_rep)

    if DEBUG_CFG.VISUAL_SPARSE_3D_TRANSFORM and 0:
      scale = 3
      print('\n\ncoords min:', coords.min(0))
      print('coords max:', coords.max(0))
      print('gt min    :', gt_bboxes[:,:4].reshape(-1,2).min(0))
      print('gt max    :', gt_bboxes[:,:4].reshape(-1,2).max(0))
      print(gt_bboxes)
      _show_3d_points_objs_ls([coords], objs_ls=[gt_bboxes], obj_rep=self.obj_rep)

    # map labels not used for evaluation to ignore_label
    if self.input_transform is not None:
      coords, feats, labels, gt_bboxes, img_meta = self.input_transform(
              coords, feats, labels, gt_bboxes, img_meta)
    if self.target_transform is not None:
      coords, feats, labels = self.target_transform(coords, feats, labels)
    if self.IGNORE_LABELS is not None:
      labels = np.array([self.label_map[x] for x in labels], dtype=np.int)

    # Use coordinate features if config is set
    if self.AUGMENT_COORDS_TO_FEATS:
      coords, feats, labels = self._augment_coords_to_feats(coords, feats, labels)

    if self.NORMALIZATION:
      feats = self._normalization(feats)
    feats = self.select_data_types(feats)

    if is_include_gt_bboxes:
      gt_labels = img_info['gt_labels']
      mask = gt_labels > 0
      gt_bboxes = gt_bboxes[mask]
      gt_bboxes[:,:4] += self.bev_pad_pixels
      img_info['gt_bboxes'] = gt_bboxes.astype(np.float32)
      img_info['gt_labels'] = gt_labels[mask]

    img_meta['dynamic_vox_size_aug'] = coords.max(0)+1
    img_info['img_meta'] = img_meta
    #print(img_meta['data_aug'])

    check_shape = 1
    if check_shape:
      assert all(img_meta['dynamic_vox_size_aug'] == coords.max(0) +1)

    assert (coords.min(axis=0)==0).all()

    if DEBUG_CFG.VISUAL_SPARSE_3D_TRANSFORM and 1:
      scale = 3
      print('\n\ndataset item')
      print('coords num:', coords.shape[0])
      print('coords min:', coords.min(0))
      print('coords max:', coords.max(0))
      print('gt min    :', gt_bboxes[:,:4].reshape(-1,2).min(0))
      print('gt max    :', gt_bboxes[:,:4].reshape(-1,2).max(0))
      #print(gt_bboxes)
      _show_3d_points_objs_ls([coords], objs_ls=[gt_bboxes], obj_rep=self.obj_rep)
      pass

    return_args = [coords, feats, labels, img_info]
    #if self.return_transformation:
    #  return_args.append(transformation.astype(np.float32))

    if self.save_sparse_input_for_debug:
      self.save_sparse_input( coords, feats, labels, img_info )
    return tuple(return_args)


class TemporalVoxelizationDataset(VoxelizationDataset):

  IS_TEMPORAL = True

  def __init__(self,
               data_paths,
               prevoxel_transform=None,
               input_transform=None,
               target_transform=None,
               data_root='/',
               ignore_label=255,
               temporal_dilation=1,
               temporal_numseq=3,
               return_transformation=False,
               augment_data=False,
               config=None,
               **kwargs):
    VoxelizationDataset.__init__(
        self,
        data_paths,
        prevoxel_transform=prevoxel_transform,
        input_transform=input_transform,
        target_transform=target_transform,
        data_root=data_root,
        ignore_label=ignore_label,
        return_transformation=return_transformation,
        augment_data=augment_data,
        config=config,
        **kwargs)
    self.temporal_dilation = temporal_dilation
    self.temporal_numseq = temporal_numseq
    temporal_window = temporal_dilation * (temporal_numseq - 1) + 1
    self.numels = [len(p) - temporal_window + 1 for p in self.data_paths]
    if any([numel <= 0 for numel in self.numels]):
      raise ValueError('Your temporal window configuration is too wide for '
                       'this dataset. Please change the configuration.')

  def load_world_pointcloud(self, filename):
    raise NotImplementedError

  def __getitem__(self, index):
    for seq_idx, numel in enumerate(self.numels):
      if index >= numel:
        index -= numel
      else:
        break

    numseq = self.temporal_numseq
    if self.augment_data and self.config.temporal_rand_numseq:
      numseq = random.randrange(1, self.temporal_numseq + 1)
    dilations = [self.temporal_dilation for i in range(numseq - 1)]
    if self.augment_data and self.config.temporal_rand_dilation:
      dilations = [random.randrange(1, self.temporal_dilation + 1) for i in range(numseq - 1)]
    files = [self.data_paths[seq_idx][index + sum(dilations[:i])] for i in range(numseq)]

    world_pointclouds = [self.load_world_pointcloud(f) for f in files]
    ptcs, centers = zip(*world_pointclouds)

    # Downsample pointcloud for speed and memory
    if self.PREVOXELIZATION_VOXEL_SIZE is not None:
      new_ptcs = []
      for ptc in ptcs:
        inds = ME.utils.sparse_quantize(
            ptc[:, :3] / self.PREVOXELIZATION_VOXEL_SIZE, return_index=True)
        new_ptcs.append(ptc[inds])
      ptcs = new_ptcs

    # Apply prevoxel transformations
    ptcs = [self.prevoxel_transform(ptc) for ptc in ptcs]

    coords, feats, labels = zip(*ptcs)
    outs = self.voxelizer.voxelize_temporal(
        coords, feats, labels, centers=centers, return_transformation=self.return_transformation)

    if self.return_transformation:
      coords_t, feats_t, labels_t, transformation_t = outs
    else:
      coords_t, feats_t, labels_t = outs

    joint_coords = np.vstack([
        np.hstack((coords, np.ones((coords.shape[0], 1)) * i)) for i, coords in enumerate(coords_t)
    ])
    joint_feats = np.vstack(feats_t)
    joint_labels = np.hstack(labels_t)

    # map labels not used for evaluation to ignore_label
    if self.input_transform is not None:
      joint_coords, joint_feats, joint_labels = self.input_transform(joint_coords, joint_feats,
                                                                     joint_labels)
    if self.target_transform is not None:
      joint_coords, joint_feats, joint_labels = self.target_transform(joint_coords, joint_feats,
                                                                      joint_labels)
    if self.IGNORE_LABELS is not None:
      joint_labels = np.array([self.label_map[x] for x in joint_labels], dtype=np.int)

    return_args = [joint_coords, joint_feats, joint_labels]
    if self.return_transformation:
      pointclouds = np.vstack([
          np.hstack((pointcloud[0][:, :6], np.ones((pointcloud[0].shape[0], 1)) * i))
          for i, pointcloud in enumerate(world_pointclouds)
      ])
      transformations = np.vstack(
          [np.hstack((transformation, [i])) for i, transformation in enumerate(transformation_t)])

      return_args.extend([pointclouds.astype(np.float32), transformations.astype(np.float32)])
    return tuple(return_args)

  def __len__(self):
    num_data = sum(self.numels)
    return num_data


def initialize_data_loader(DatasetClass,
                           config,
                           phase,
                           num_workers,
                           shuffle,
                           repeat,
                           augment_data,
                           batch_size,
                           limit_numpoints,
                           input_transform=None,
                           target_transform=None):
  if isinstance(phase, str):
    phase = str2datasetphase_type(phase)

  if config.return_transformation:
    collate_fn = t.cflt_collate_fn_factory(limit_numpoints)
  else:
    collate_fn = t.cfl_collate_fn_factory(limit_numpoints)

  prevoxel_transform_train = []
  if augment_data:
    prevoxel_transform_train.append(t.ElasticDistortion(DatasetClass.ELASTIC_DISTORT_PARAMS))

  if len(prevoxel_transform_train) > 0:
    prevoxel_transforms = t.Compose(prevoxel_transform_train)
  else:
    prevoxel_transforms = None

  input_transforms = []
  if input_transform is not None:
    input_transforms += input_transform

  if augment_data:
    input_transforms += [
        t.RandomDropout(0.2),
        t.RandomHorizontalFlip(DatasetClass.ROTATION_AXIS, DatasetClass.IS_TEMPORAL),
        t.ChromaticAutoContrast(),
        t.ChromaticTranslation(config.data_aug_color_trans_ratio),
        t.ChromaticJitter(config.data_aug_color_jitter_std),
        # t.HueSaturationTranslation(config.data_aug_hue_max, config.data_aug_saturation_max),
    ]

  if len(input_transforms) > 0:
    input_transforms = t.Compose(input_transforms)
  else:
    input_transforms = None

  dataset = DatasetClass(
      config,
      prevoxel_transform=prevoxel_transforms,
      input_transform=input_transforms,
      target_transform=target_transform,
      cache=config.cache_data,
      augment_data=augment_data,
      phase=phase)

  data_args = {
      'dataset': dataset,
      'num_workers': num_workers,
      'batch_size': batch_size,
      'collate_fn': collate_fn,
  }

  if repeat:
    data_args['sampler'] = InfSampler(dataset, shuffle)
  else:
    data_args['shuffle'] = shuffle

  data_loader = DataLoader(**data_args)

  return data_loader
