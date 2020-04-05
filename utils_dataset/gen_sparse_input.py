from MinkowskiEngine import SparseTensor
import numpy as np
import torch

from configs.common import SPARSE_BEV
from tools.debug_utils import _show_3d_points_bboxes_ls, _show_lines_ls_points_ls

def get_pcl_topview(sinput, gt_bboxes):
  '''
  9 channels: [color, normal, coords]
  '''
  sinput.F[:,6:] = 1
  dense_t , _, _ = sinput.dense()
  zdim =  dense_t.shape[-1]
  bev_d = dense_t.mean(-1)
  bev_d = bev_d[:, :7, ...]
  batch_size = bev_d.shape[0]

  #bev_d = bev_d.permute(0,1,3,2)

  h, w = bev_d.shape[2:]
  grid_y, grid_x = torch.meshgrid( torch.arange(h), torch.arange(w) )
  bev_coords_base = torch.cat([grid_y[:,:,None], grid_x[:,:,None]],  dim=2).view(-1, 2).int()
  bev_coords = []
  for i in range(batch_size):
    batch_inds = (torch.ones(h*w,1)*i).int()
    third_inds = (torch.ones(h*w,1)*0).int()
    bev_coords_i = torch.cat([ batch_inds, bev_coords_base, third_inds ], dim=1)
    bev_coords.append(bev_coords_i)
  bev_coords = torch.cat(bev_coords, dim=0)

  bev_sfeat = bev_d.permute(0,2,3, 1).reshape(-1, bev_d.shape[1])
  mask = bev_sfeat[:,-1] > 1e-5
  bev_coords = bev_coords[mask]
  bev_sfeat = bev_sfeat[mask]

  bev_sparse = SparseTensor(bev_sfeat, bev_coords)

  if 0:
    for i in range(batch_size):
      bev_i = bev_d[i]
      bev_i = bev_i.permute(2,1,0)
      lines2d = gt_bboxes[i].cpu().data.numpy()
      density = bev_i[..., -1].cpu().data.numpy()
      color = bev_i[..., :3].cpu().data.numpy()
      normal = bev_i[..., 3:6].cpu().data.numpy()
      _show_lines_ls_points_ls( density, [lines2d] )
      _show_lines_ls_points_ls( color, [lines2d] )
      _show_lines_ls_points_ls( normal, [lines2d] )
      pass

  return bev_sparse

def prepare_sparse_input(img, img_meta=None, gt_bboxes=None, gt_labels=None, rescale=None):
  coords_batch, feats_batch = img
  ## For some networks, making the network invariant to even, odd coords is important
  #coord_base = (torch.rand(3) * 100).type_as(coords_batch)
  #coords_batch[:, 1:4] += coord_base

  sinput = SparseTensor(feats_batch, coords_batch)
  if SPARSE_BEV:
    sinput = get_pcl_topview(sinput, gt_bboxes)

  if 0:
    coords_batch = sinput.C
    feats_batch = sinput.F

    dense, _, _ = sinput.dense()
    dense = dense.permute(0,1,3,2,4)
    batch_size = coords_batch[:,0].max()+1
    for i in range(batch_size):
      lines2d = gt_bboxes[i].cpu().data.numpy()
      density = dense[i,-1,:,:,0].cpu().data.numpy()
      _show_lines_ls_points_ls(density, [lines2d])
      pass

  if 0:
    n = coords_batch.shape[0]
    print(f'batch voxe num: {n/1000}K')

    batch_size = coords_batch[:,0].max()+1
    for i in range(batch_size):
      print(f'example {i}/{batch_size}')
      batch_mask = coords_batch[:,0] == i
      points = coords_batch[batch_mask][:, 1:].cpu().data.numpy()
      colors = feats_batch[batch_mask][:, :3].cpu().data.numpy()
      colors = colors+0.5
      np = points.shape[0]

      img_meta_i = img_meta[i]
      voxel_size = img_meta_i['voxel_size']
      raw_dynamic_vox_size = img_meta_i['raw_dynamic_vox_size']

      mask_i = sinput.C[:,0] == i
      Ci = sinput.C[mask_i]

      lines2d = gt_bboxes[i].cpu().data.numpy()


      from beike_data_utils.line_utils import lines2d_to_bboxes3d
      from configs.common import OBJ_REP
      bboxes3d_pixel = lines2d_to_bboxes3d(lines2d, OBJ_REP, height=30, thickness=1)

      min_points = points.min(axis=0)
      max_points = points.max(axis=0)
      min_lines = lines2d[:,:4].reshape(-1,2).min(axis=0)
      max_lines = lines2d[:,:4].reshape(-1,2).max(axis=0)

      data_aug = img_meta_i['data_aug']
      dynamic_vox_size_aug = img_meta_i['dynamic_vox_size_aug']
      print('\n\nfinal sparse input')
      footprint = dynamic_vox_size_aug[0] * dynamic_vox_size_aug[1]
      print(f'dynamic_vox_size_aug: {dynamic_vox_size_aug}, footprint: {footprint}')

      print(f'num voxel: {np/1000}K')
      print(img_meta[i]['filename'])
      print(f'points scope: {min_points} - {max_points}')
      print(f'lines scope: {min_lines} - {max_lines}')
      print(f'data aug:\n {data_aug}\n')

      scale = 1
      _show_lines_ls_points_ls((512,512), [lines2d*scale], [points*scale])

      _show_3d_points_bboxes_ls([points], [colors], [ bboxes3d_pixel ],
                  b_colors = 'red', box_oriented=True)
      pass
  return sinput


def update_img_shape_for_pcl(x, img_meta, point_strides):
  img_meta['feat_sizes'] = [np.array( [*xi.size()[2:]] ) for xi in x]
  img_meta['pad_shape'] = img_meta['feat_sizes'][0] * point_strides[0]
  img_meta['img_shape'] = img_meta['pad_shape']
