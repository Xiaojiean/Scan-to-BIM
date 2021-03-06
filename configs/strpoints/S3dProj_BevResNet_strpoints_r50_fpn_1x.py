# model settings
''' modified
  num_points
'''
''' # pedding
  num_outs
  assigner
  img_norm_cfg
  transform_method
'''
import math
from configs.common import DIM_PARSE, DEBUG_CFG
DATA = 'beike_pcl_2d'
DATA = 'stanford_pcl_2d'
classes= ['wall']

voxel_size = 0.04

if DATA == 'beike_pcl_2d':
  stem_stride = 4
  batch_size = {2:2, 4:6}[stem_stride]
  _obj_rep = 'XYXYSin2'
  _transform_method='moment_XYXYSin2'

elif DATA == 'stanford_pcl_2d':
  stem_stride = 2
  batch_size = {2:3, 4:6}[stem_stride]
  _obj_rep = 'Rect4CornersZ0Z1'
  _transform_method = 'sort_4corners'

dim_parse = DIM_PARSE(_obj_rep, len(classes)+1)
_obj_dim = dim_parse.OBJ_DIM

if DATA == 'beike_pcl_2d':
  # pcl_scope: max=[20.041 15.847  6.531] mean=[10.841 10.851  3.392]
  max_height = 7.68
  max_height = 5
elif DATA == 'stanford_pcl_2d':
  max_height = 5.12
max_zdim = max_height / voxel_size
bev_pad_pixels = stem_stride * 0
#*******************************************************************************

if _obj_rep == 'RoLine2D_UpRight_xyxy_sin2a':
  _transform_method='moment_lscope_istopleft'
#*******************************************************************************
if DATA == 'stanford_pcl_2d':
  dataset_type = 'StanfordPclDataset'
  data_root = f'data/stanford/'
  ann_file = data_root
  in_channels = 9

if DATA == 'beike_pcl_2d':
  dataset_type = 'BeikePclDataset'
  data_root = f'data/beike/processed_512/'
  ann_file = data_root + 'json/'
  in_channels = 9

#*******************************************************************************
max_planes = 1024
norm_cfg = dict(type='GN', num_groups=32, requires_grad=True)

point_strides_all = [(2**i)*stem_stride for i in range(4)]
bbp = 32
model = dict(
    type='StrPointsDetector',
    pretrained=None,
    backbone=dict(
        type='S3dProj_BevResNet',
        depth=50,
        in_channels=in_channels,
        num_stages=4,
        out_indices=(0,1,2,3),
        frozen_stages=-1,
        style='pytorch',
        basic_planes=bbp,
        max_planes=max_planes,
        stem_stride=stem_stride,
        bev_pad_pixels=bev_pad_pixels,
        max_zdim=max_zdim),
    neck=dict(
        type='FPN',
        in_channels=[ bbp*4, bbp*8, bbp*16, bbp*32],
        out_channels=256,
        start_level=0,
        add_extra_convs=True,
        num_outs=4,
        norm_cfg = norm_cfg,
        ),
    bbox_head=dict(
        type='StrPointsHead',
        obj_rep=_obj_rep,
        num_classes=1+len(classes),
        in_channels=256,
        feat_channels=256,
        point_feat_channels=256,
        stacked_convs=3,
        num_points=9,
        gradient_mul=0.1,
        point_strides=point_strides_all,
        point_base_scale=1,
        norm_cfg=norm_cfg,
        loss_cls=dict(
            type='FocalLoss',
            use_sigmoid=True,
            gamma=2.0,
            alpha=0.25,
            loss_weight=1.0,),
        cls_types=['refine', 'final'],
        loss_bbox_init=dict(type='SmoothL1Loss', beta=0.11, loss_weight=0.5),
        loss_bbox_refine=dict(type='SmoothL1Loss', beta=0.11, loss_weight=1.0),
        transform_method=_transform_method,
        dcn_zero_base=False,
        corner_hm = False,
        corner_hm_only = False,
        move_points_to_center = False,
        relation_cfg=dict(enable=0, stage='refine', score_threshold=0.2, max_relation_num=120),
        adjust_5pts_by_4=True,
        )
    )
        #transform_method='minmax'))
        #transform_method='center_size_istopleft'))
# training and testing settings
train_cfg = dict(
    init=dict(
        assigner=dict(type='PointAssigner', scale=4, pos_num=1, obj_rep=_obj_rep),
        allowed_border=-1,
        pos_weight=-1,
        debug=False),
    refine=dict(
        assigner=dict(
            type='MaxIoUAssigner',
            pos_iou_thr=0.7,
            neg_iou_thr=0.4,
            min_pos_iou=0.1,
            ignore_iof_thr=-1,
            overlap_fun='dil_iou_dis_rotated_3d',
            obj_rep=_obj_rep),
        allowed_border=-1,
        pos_weight=-1,
        debug=False),
    corner=dict(
        assigner=dict(
            type='MaxIoUAssigner',
            pos_iou_thr=0.6,
            neg_iou_thr=0.1,
            min_pos_iou=0,
            ignore_iof_thr=-1,
            overlap_fun='dis',
            ref_radius=2,
            obj_rep='corner'),
        allowed_border=-1,
        pos_weight=-1,
        gaussian_weight=True,
        debug=False),
        )
test_cfg = dict(
    nms_pre=1000,
    min_bbox_size=0,
    score_thr=0.2,
    nms=dict(type='nms_rotated', iou_thr=0.3, min_width_length_ratio=0.3),
    max_per_img=150)

# dataset settings



#img_norm_cfg = dict(
#    mean=[  0, 0,0,0],
#    std=[ 255, 1,1,1 ], to_rgb=False, method='raw')

img_norm_cfg = dict(
    mean=[  4.753,  0.,     0.,    0.],
    std=[ 16.158,  0.155,  0.153,  0.22], to_rgb=False, method='rawstd') # better

#img_norm_cfg = dict(
#    mean=[4.753, 0.044, 0.043, 0.102],
#    std=[ 16.158,  0.144,  0.142,  0.183], to_rgb=False, method='abs')
#
#img_norm_cfg = dict(
#    mean=[4.753, 11.142, 11.044, 25.969],
#    std=[ 16.158, 36.841, 36.229, 46.637], to_rgb=False, method='abs255')


lra = 0.01


if DATA == 'beike_pcl_2d':
  max_footprint_for_scale = 200
  max_num_points = 30 * 10000
  img_prefix_train = data_root + f'train.txt'
  img_prefix_test = data_root + f'test.txt'
  img_prefix_test = img_prefix_train
if DATA == 'stanford_pcl_2d':
  max_footprint_for_scale = 50 # 200
  max_num_points = 5 * 10000
  img_prefix_train = '123456'
  img_prefix_test = '5'
  img_prefix_test = '24'
  #img_prefix_test = '136'

data = dict(
    imgs_per_gpu=batch_size,
    workers_per_gpu=0,
    train=dict(
        type=dataset_type,
        obj_rep = _obj_rep,
        ann_file=ann_file,
        img_prefix=img_prefix_train,
        voxel_size=voxel_size,
        augment_data=True,
        data_types = ['color', 'norm', 'xyz'],
        max_num_points=max_num_points,
        max_footprint_for_scale=max_footprint_for_scale,
        filter_edges=True,
        classes = classes,
        bev_pad_pixels = bev_pad_pixels,
        pipeline=None),
    val=None,
    test=None,
)
data['val'] = data['train'].copy()
data['val']['img_prefix'] = img_prefix_test
data['test'] = data['val'].copy()


# optimizer
optimizer = dict(type='SGD', lr=lra, momentum=0.9, weight_decay=0.0001)
optimizer_config = dict(grad_clip=dict(max_norm=35, norm_type=2))
# learning policy
total_epochs = 510
lr_config = dict(
    policy='step',
    warmup='linear',
    warmup_iters=20,
    warmup_ratio=1.0 / 3,
    step=[int(total_epochs*0.4), int(total_epochs*0.7)])
checkpoint_config = dict(interval=10)
# yapf:disable
log_config = dict(
    interval=1,
    hooks=[
        dict(type='TextLoggerHook'),
        dict(type='TensorboardLoggerHook')
    ])
# yapf:enable
# runtime settings
dist_params = dict(backend='nccl')
log_level = 'INFO'

if DATA == 'beike_pcl_2d':
  work_dir = f'./work_dirs/KR50_fpn'
  load_from = './checkpoints/beike/Apr27_Bk_wado_Pcl.pth'
if DATA == 'stanford_pcl_2d':
  work_dir = f'./work_dirs/SR50_fpn'
  load_from = './checkpoints/sfd/15May_Pcl_abcdi_train_6as.pth'
load_from = None
resume_from = None
auto_resume = True
workflow = [('train', 5), ('val', 1)]

if 1:
  data['workers_per_gpu'] = 0
  total_epochs = 510
  checkpoint_config = dict(interval=50)
  workflow = [('train', 1),]

