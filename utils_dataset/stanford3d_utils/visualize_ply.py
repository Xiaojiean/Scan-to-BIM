from plyfile import PlyData
from collections import defaultdict
import numpy as np
from tools.visual_utils import _show_3d_points_objs_ls
from tools.visual_utils import _show_objs_ls_points_ls, _show_3d_points_objs_ls
import glob

_classes = ['clutter', 'beam', 'board', 'bookcase', 'ceiling', 'chair', 'column',
            'door', 'floor', 'sofa', 'stairs', 'table', 'wall', 'window', 'room']
_category_ids_map = {cat:i for i,cat in enumerate(_classes)}

def load_1_ply(filepath):
    plydata = PlyData.read(filepath)
    data = plydata.elements[0].data
    coords = np.array([data['x'], data['y'], data['z']], dtype=np.float32).T
    feats = np.array([data['red'], data['green'], data['blue']], dtype=np.float32).T
    labels = np.array(data['label'], dtype=np.int32)
    instance = np.array(data['instance'], dtype=np.int32)
    #_show_3d_points_objs_ls([coords])
    return coords, feats, labels, None


def load_bboxes(pcl_file):
  anno_file = pcl_file.replace('.ply', '.npy').replace('Area_','Boxes_Area_')
  scope_file = pcl_file.replace('.ply', '-scope.txt')
  anno = defaultdict(list)

  bboxes_dict = np.load(anno_file, allow_pickle=True).tolist()
  bboxes = []
  bbox_cat_ids = []
  for cat in bboxes_dict:
    classes = ['beam', 'wall', 'column', 'window', 'door']
    classes = ['beam', 'wall', 'column', 'window', ]
    #classes = ['door']
    #classes = ['window']
    if cat not in classes:
      continue
    bboxes.append( bboxes_dict[cat] )
    num_box = bboxes_dict[cat].shape[0]
    cat_ids = _category_ids_map[cat] * np.ones([num_box], dtype=np.int64)
    bbox_cat_ids.append( cat_ids )
  if len(bboxes) == 0:
    bboxes_3d = np.zeros([0,8])
    bboxes_2d = np.zeros([0,5])
  else:
    bboxes_3d = np.concatenate(bboxes, axis=0)

    scope = np.loadtxt(scope_file)
    anno['pcl_scope'] = scope

    #bboxes_3d[:, :2] -= scope[0:1,:2]
    #bboxes_3d[:, 2:4] -= scope[0:1,:2]

    # RoBox3D_UpRight_xyxy_sin2a_thick_Z0Z1  to   RoLine2D_UpRight_xyxy_sin2a
    bboxes_2d = bboxes_3d[:, :5]
    bbox_cat_ids = np.concatenate(bbox_cat_ids)

  filename = pcl_file
  anno['filename'] = filename
  anno['bboxes_3d'] = bboxes_3d
  anno['bboxes_2d'] = bboxes_2d
  anno['bbox_cat_ids'] = bbox_cat_ids

  #show_bboxes(bboxes_3d)
  return anno

def cut_roof(points, feats):
  z_min = points[:,2].min()
  z_max = points[:,2].max()
  z_th = z_min  + (z_max - z_min) * 0.7
  mask = points[:,2] < z_th
  return points[mask], feats[mask]


def show_bboxes(bboxes_3d, points=None, feats=None, obj_rep_in=None):
    n = points.shape[0] / 1000
    print(f'num points: {n} K')
    points, feats = cut_roof(points, feats)
    num_p = points.shape[0]
    choices = np.random.choice(num_p, 2*10000)
    #points = points[choices]
    #_show_3d_points_objs_ls(None, None, [bboxes_3d],  obj_rep='RoBox3D_UpRight_xyxy_sin2a_thick_Z0Z1')
    bboxes_show = bboxes_3d.copy()
    voxel_size = 0.02
    bboxes_show[:,:4] /= voxel_size
    bboxes_show[:,:4] += 10
    points_ls = [points] if points is not None else None
    feats_ls = [feats] if feats is not None else None
    #_show_objs_ls_points_ls( (512,512), [bboxes_show], obj_rep=obj_rep_in)
    #_show_objs_ls_points_ls( (512,512), [bboxes_show[:,:6]], obj_rep='RoBox2D_UpRight_xyxy_sin2a_thick' )
    _show_3d_points_objs_ls(obj_rep=obj_rep_in, objs_ls=[bboxes_3d, bboxes_3d], obj_colors=['random', 'black'],  box_types=['surface_mesh', 'line_mesh'] )
    _show_3d_points_objs_ls(points_ls, feats_ls)
    #_show_3d_points_objs_ls(points_ls, feats_ls, obj_rep_in, objs_ls=[bboxes_3d])



def get_scene_name(filepath):
  import pdb; pdb.set_trace()  # XXX BREAKPOINT
  pass
def main():
  data_root = '/DS/Stanford3D/aligned_processed_instance/'
  files = glob.glob(data_root+'Area*/*.ply')
  for i, f in enumerate(files):
    if i < 5:
      continue
    print(f)
    coords, feats, labels, _ = load_1_ply(f)
    obj_rep='XYXYSin2WZ0Z1'
    anno = load_bboxes(f)
    show_bboxes(anno['bboxes_3d'], coords, feats, obj_rep)
  pass

if __name__ == '__main__':
  main()
