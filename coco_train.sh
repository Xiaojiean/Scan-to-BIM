#export CUDA_VISIBLE_DEVICES=1

CONFIG=configs/reppoints/d_reppoints_moment_r50_fpn_2x.py
#CONFIG=configs/reppoints/d2_reppoints_moment_r50_fpn_2x.py
#CONFIG=configs/reppoints/reppoints_moment_r50_fpn_2x.py
#CONFIG=configs/reppoints/reppoints_moment_r101_dcn_fpn_2x.py
CONFIG=configs/fcos/d_fcos_r50_caffe_fpn_gn_1x_1gpu.py



ipython tools/train.py -- ${CONFIG} 
#./tools/dist_train.sh ${CONFIG} 2