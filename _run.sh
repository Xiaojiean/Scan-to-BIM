# xyz

#export CUDA_LAUNCH_BLOCKING=1
#export CUDA_VISIBLE_DEVICES=1

CONFIG=configs/strpoints/bev_strpoints_r50_fpn_1x.py
#CONFIG=configs/strpoints/S3dProj_BevResNet_strpoints_r50_fpn_1x.py


wkdir=sTPV_r50_fpn_Rect4CornersZ0Z1_Apts4_stanford2d_wabecodowifl_bs6_lr10_LsW510R2P1N1_Rfiou741_Fpn44_Pbs1_Bp32_AreaL12356
CP=./work_dirs/${wkdir}/loss1d5.pth
#CONFIG=./work_dirs/${wkdir}/_S3dProj_BevResNet_strpoints_r50_fpn_1x.py
CONFIG=./work_dirs/${wkdir}/_bev_strpoints_r50_fpn_1x.py
#CP=./checkpoints/beike/Apr23_WaDo_Bev.pth
#CP=./checkpoints/sfd/15May_Pcl_abcdi_train_6as.pth


LR=0.01
ROTATE=1
BASE_PLANE=32
BS=6
DATA_TYPES=cnx
FILTER_EDGES=0
REL=0
CLS=abcdif
#CLS=ad
#CLS=a
#CLS=A

#CLS=acd
#CLS=bif

#ipython tools/train.py --  ${CONFIG} --rotate $ROTATE --lr $LR --base_plane $BASE_PLANE --bs $BS  --data_types $DATA_TYPES  --filter_edges $FILTER_EDGES  --classes $CLS --relation $REL  
#--resume $CP 

#./tools/dist_train.sh ${CONFIG} 2 --rotate $ROTATE   --lr $LR --base_plane $BASE_PLANE   --data_types $DATA_TYPES  --filter_edges $FILTER_EDGES  --classes $CLS   --relation $REL
#--resume $CP 


ROTATE=0
STYLE='--out ./work_dirs/'${wkdir}'/detection.pickle --eval bbox'
#STYLE=--show

ipython tools/test.py --  ${CONFIG} $CP --rotate $ROTATE   $STYLE --base_plane $BASE_PLANE   --data_types $DATA_TYPES  --filter_edges $FILTER_EDGES   --classes $CLS  --relation $REL
