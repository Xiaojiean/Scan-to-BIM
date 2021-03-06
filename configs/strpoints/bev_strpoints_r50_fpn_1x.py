''' # pedding
  num_outs
  assigner
  img_norm_cfg
  transform_method
'''

TOPVIEW = 'VerD' # better
#*******************************************************************************
from configs.common import DIM_PARSE, Track_running_stats
IMAGE_SIZE = DIM_PARSE.IMAGE_SIZE
DATA = 'beike2d'
#DATA = 'stanford2d'
classes= ['wall']
#classes= ['room']

if DATA == 'beike2d':
  _obj_rep = 'XYXYSin2'
  _transform_method='moment_XYXYSin2'

  #_obj_rep = 'XYXYSin2WZ0Z1'
  #_transform_method='moment_XYXYSin2WZ0Z1'
  _obj_rep_out = _obj_rep

  if 'room' in classes:
    _obj_rep = 'XYXYSin2WZ0Z1'
    _transform_method = ['XYDRSin2Cos2Z0Z1', 'moment_std_XYDRSin2Cos2Z0Z1', 'moment_max_XYDRSin2Cos2Z0Z1'][1]
    _obj_rep_out='XYDRSin2Cos2Z0Z1'

elif DATA == 'stanford2d':
  _obj_rep = 'Rect4CornersZ0Z1'
  _transform_method = 'sort_4corners'

dim_parse = DIM_PARSE(_obj_rep, len(classes)+1)
_obj_dim = dim_parse.OBJ_DIM

#*******************************************************************************
cls_groups = None
#cls_groups = [[1], [2]]
#*******************************************************************************
norm_cfg = dict(type='GN', num_groups=32, requires_grad=True)

model = dict(
    type='StrPointsDetector',
    pretrained=None,
    backbone=dict(
        type='ResNet',
        depth=50,
        in_channels=4,
        num_stages=4,
        out_indices=( 0, 1, 2, 3),
        frozen_stages=-1,
        style='pytorch',
        basic_planes=64,
        max_planes=2048),
    neck=dict(
        type='FPN',
        in_channels=[ 256, 512, 1024, 2048],
        out_channels=256,
        start_level=0,
        add_extra_convs=True,
        num_outs=4,
        norm_cfg=norm_cfg),
    bbox_head=dict(
        type='StrPointsHead',
        obj_rep=_obj_rep,
        classes=classes,
        in_channels=256,
        feat_channels=256,
        point_feat_channels=256,
        stacked_convs=3,
        num_points=9,
        gradient_mul=0.1,
        point_strides=[4, 8, 16, 32],
        point_base_scale=1,
        norm_cfg=norm_cfg,
        loss_cls=dict(
            type='FocalLoss',
            use_sigmoid=True,
            gamma=2.0,
            alpha=0.25,
            loss_weight=10.0,),
        cls_types=['refine', 'final'],
        loss_bbox_init=dict(type='SmoothL1Loss', beta=0.11, loss_weight=0.5),
        loss_bbox_refine=dict(type='SmoothL1Loss', beta=0.11, loss_weight=1.0),
        transform_method=_transform_method,
        dcn_zero_base=False,
        corner_hm = False,
        corner_hm_only = False,
        move_points_to_center = 0,
        relation_cfg=dict(enable=0,
                          stage='refine',
                          score_threshold=0.2,
                          max_relation_num=120),
        adjust_5pts_by_4=False,
        cls_groups = cls_groups,
        )
    )
        #transform_method='minmax'))
        #transform_method='center_size_istopleft'))
# training and testing settings
train_cfg = dict(
    init=dict(
        assigner=dict(type='PointAssigner', scale=4, pos_num=1, obj_rep=_obj_rep_out),
        allowed_border=-1,
        pos_weight=-1,
        debug=False),
    refine=dict(
        assigner=dict(
            type='MaxIoUAssigner',
            pos_iou_thr=0.65,
            neg_iou_thr=0.3,
            min_pos_iou=0.1,
            ignore_iof_thr=-1,
            overlap_fun='dil_iou_dis_rotated_3d',
            obj_rep=_obj_rep_out),
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
# ops/nms/nms_wrapper.py
test_cfg = dict(
    nms_pre=1000,
    min_bbox_size=0,
    score_thr=0.2,
    nms=dict(type='nms_rotated', iou_thr=0.2, min_width_length_ratio=0.3),
    max_per_img=150)
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

train_pipeline = [
    dict(type='LoadTopviewFromFile'),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(type='PadToSameHW_ForRotation',obj_rep=_obj_rep,pad_border_make_bboxes_pos=True),
    dict(type='ResizeImgLine', obj_rep=_obj_rep, img_scale=(IMAGE_SIZE, IMAGE_SIZE), keep_ratio=True, obj_dim=_obj_dim),
    dict(type='RandomLineFlip', flip_ratio=0.7, obj_rep=_obj_rep, direction='random'),
    dict(type='RandomRotate', rotate_ratio=0.9, obj_rep=_obj_rep),
    dict(type='NormalizeTopview', **img_norm_cfg),
    dict(type='DefaultFormatBundle'),
    dict(type='Collect', keys=['img', 'gt_bboxes', 'gt_labels', 'gt_relations']),
]
test_pipeline = [
    dict(type='LoadTopviewFromFile'),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(
        type='MultiScaleFlipAug',
        img_scale=(IMAGE_SIZE, IMAGE_SIZE),
        flip=False,
        transforms=[
            dict(type='PadToSameHW_ForRotation', obj_rep=_obj_rep, pad_border_make_bboxes_pos=True),
            dict(type='ResizeImgLine', obj_rep=_obj_rep, keep_ratio=True, obj_dim=_obj_dim),
            dict(type='RandomLineFlip', obj_rep=_obj_rep),
            dict(type='RandomRotate', rotate_ratio=0.0, obj_rep=_obj_rep),
            dict(type='NormalizeTopview', **img_norm_cfg),
            dict(type='ImageToTensor', keys=['img', 'gt_bboxes', 'gt_labels', 'gt_relations']),
            dict(type='Collect', keys=['img', 'gt_bboxes', 'gt_labels', 'gt_relations']),
        ])
]

filter_edges=True
# dataset settings
if DATA == 'beike2d':
  dataset_type = 'BeikeDataset'
  data_root = f'data/beike/processed_{IMAGE_SIZE}/'
  ann_file = data_root + 'json/'
  img_prefix_train = data_root + f'TopView_{TOPVIEW}/train.txt'
  img_prefix_test = data_root + f'TopView_{TOPVIEW}/test.txt'
  #img_prefix_test = img_prefix_train

elif DATA == 'stanford2d':
  dataset_type = 'Stanford_2D_Dataset'
  ann_file = 'data/stanford/'
  img_prefix_train = '12356'
  img_prefix_test = '5'
  img_prefix_test = '4'
  #img_prefix_test = '136'

data = dict(
    imgs_per_gpu=7,
    workers_per_gpu=2,
    train=dict(
        type=dataset_type,
        obj_rep = _obj_rep,
        ann_file=ann_file,
        img_prefix=img_prefix_train,
        pipeline=train_pipeline,
        classes=classes,
        filter_edges=filter_edges),
    val=dict(
        type=dataset_type,
        obj_rep = _obj_rep,
        ann_file=ann_file,
        img_prefix=img_prefix_test,
        pipeline=train_pipeline,
        classes=classes,
        filter_edges=filter_edges),
    test=dict(
        type=dataset_type,
        obj_rep = _obj_rep,
        obj_rep_out = _obj_rep_out,
        ann_file=ann_file,
        img_prefix=img_prefix_test,
        pipeline=test_pipeline,
        classes=classes,
        filter_edges=filter_edges))
# optimizer
optimizer = dict(type='SGD', lr=0.01, momentum=0.9, weight_decay=0.0001)
optimizer_config = dict(grad_clip=dict(max_norm=35, norm_type=2))
# learning policy
total_epochs =  500
lr_config = dict(
    policy='step',
    warmup='linear',
    warmup_iters=20,
    warmup_ratio=1.0 / 3,
    step=[int(total_epochs*0.5), int(total_epochs*0.8)])
checkpoint_config = dict(interval=1)
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
tra_run = '' if Track_running_stats else '_nTrun'
work_dir = f'./work_dirs/{DATA[0]}TPV_r50_fpn{tra_run}_{_obj_rep}'
if _transform_method == 'moment_std_XYDRSin2Cos2Z0Z1':
  work_dir += '_Std_'
if _transform_method == 'moment_max_XYDRSin2Cos2Z0Z1':
  work_dir += '_Max_'
if DATA == 'beike2d':
  load_from = './checkpoints/beike/jun15_wd_bev.pth'
  load_from = './checkpoints/beike/jun17_wd_bev_L_S2.pth'
  if 'room' in classes:
    load_from = './checkpoints/beike/jun14_room_bev.pth'
    load_from = './checkpoints/beike/jun18_r_bev_L.pth'
elif DATA == 'stanford2d':
  load_from = './checkpoints/sfd/24May_bev_abcdif_train_6as.pth'

#load_from = None
resume_from = None
auto_resume = True
workflow = [('train', 1), ('val', 1)]
if 0:
  data['workers_per_gpu'] = 0
  workflow = [('train', 1),]
  checkpoint_config = dict(interval=10)

