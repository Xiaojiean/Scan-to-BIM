import torch

from ..bbox import PseudoSampler, assign_and_sample, build_assigner
from ..utils import multi_apply

from mmdet import debug_tools
DEBUG = False


def point_target(proposals_list,
                 valid_flag_list,
                 gt_bboxes_list,
                 img_metas,
                 cfg,
                 gt_bboxes_ignore_list=None,
                 gt_labels_list=None,
                 label_channels=1,
                 sampling=True,
                 unmap_outputs=True,
                 flag=''):
    """Compute corresponding GT box and classification targets for proposals.

    Args:
        points_list (list[list]): Multi level points of each image.
        valid_flag_list (list[list]): Multi level valid flags of each image.
          padded part is invalid
        gt_bboxes_list (list[Tensor]): Ground truth bboxes of each image.
        img_metas (list[dict]): Meta info of each image.
        cfg (dict): train sample configs.


    (1) flag == 'init'
    points_list[i]: [n,3] 3 = center + stride

    (2) flag == 'refine'
    points_list[i]: [n,5] 5 = line

    Returns:
        tuple
    """
    num_imgs = len(img_metas)
    assert len(proposals_list) == len(valid_flag_list) == num_imgs

    #if DEBUG:
    #  debug_tools.show_multi_ls_shapes([proposals_list, gt_bboxes_list], ['proposals_list','gt_bboxes_list'], f'{flag} point_target input')

    # points number of multi levels
    num_level_proposals = [points.size(0) for points in proposals_list[0]]

    # concat all level points and flags to a single tensor
    for i in range(num_imgs):
        assert len(proposals_list[i]) == len(valid_flag_list[i])
        proposals_list[i] = torch.cat(proposals_list[i])
        valid_flag_list[i] = torch.cat(valid_flag_list[i])

    # compute targets for each image
    if gt_bboxes_ignore_list is None:
        gt_bboxes_ignore_list = [None for _ in range(num_imgs)]
    if gt_labels_list is None:
        gt_labels_list = [None for _ in range(num_imgs)]

    if DEBUG:
      debug_tools.show_multi_ls_shapes([proposals_list, gt_bboxes_list], ['proposals_list','gt_bboxes_list'], f'{flag} point_target (2)')

    (all_labels, all_label_weights, all_bbox_gt, all_proposals,
     all_proposal_weights, pos_inds_list, neg_inds_list) = multi_apply(
         point_target_single,
         proposals_list,
         valid_flag_list,
         gt_bboxes_list,
         gt_bboxes_ignore_list,
         gt_labels_list,
         img_metas,
         cfg=cfg,
         label_channels=label_channels,
         sampling=sampling,
         unmap_outputs=unmap_outputs,)


    # no valid points
    if any([labels is None for labels in all_labels]):
        return None
    # sampled points of all images
    num_total_pos = sum([max(inds.numel(), 1) for inds in pos_inds_list])
    num_total_neg = sum([max(inds.numel(), 1) for inds in neg_inds_list])
    num_total_gt = sum([gtb.shape[0] for gtb in gt_bboxes_list])
    labels_list = images_to_levels(all_labels, num_level_proposals)
    label_weights_list = images_to_levels(all_label_weights,
                                          num_level_proposals)
    bbox_gt_list = images_to_levels(all_bbox_gt, num_level_proposals)
    proposals_list = images_to_levels(all_proposals, num_level_proposals)
    proposal_weights_list = images_to_levels(all_proposal_weights,
                                             num_level_proposals)

    if DEBUG:
      debug_tools.show_multi_ls_shapes([all_bbox_gt], ['all_bbox_gt'], f'{flag} point_target (3)')
      print(f'pos:{num_total_pos}\nneg:{num_total_neg}\ngt:{num_total_gt}')
      show_point_targets(pos_inds_list, all_proposals, gt_bboxes_list, flag)
      pass

      #debug_tools.show_multi_ls_shapes([bbox_gt_list], ['bbox_gt_list'], f'{flag} point_target (4)')

    return (labels_list, label_weights_list, bbox_gt_list, proposals_list,
            proposal_weights_list, num_total_pos, num_total_neg)


def images_to_levels(target, num_level_grids):
    """Convert targets by image to targets by feature level.

    [target_img0, target_img1] -> [target_level0, target_level1, ...]
    """
    target = torch.stack(target, 0)
    level_targets = []
    start = 0
    for n in num_level_grids:
        end = start + n
        level_targets.append(target[:, start:end].squeeze(0))
        start = end
    return level_targets


def point_target_single(flat_proposals,
                        valid_flags,
                        gt_bboxes,
                        gt_bboxes_ignore,
                        gt_labels,
                        img_meta,
                        cfg,
                        label_channels=1,
                        sampling=True,
                        unmap_outputs=True,):
    inside_flags = valid_flags
    if not inside_flags.any():
        return (None, ) * 7
    # assign gt and sample proposals
    proposals = flat_proposals[inside_flags, :]

    if sampling:
        assign_result, sampling_result = assign_and_sample(
            proposals, gt_bboxes, gt_bboxes_ignore, None, cfg)
    else:
        bbox_assigner = build_assigner(cfg.assigner)
        assign_result = bbox_assigner.assign(proposals, gt_bboxes,
                                             gt_bboxes_ignore, gt_labels,
                                             img_meta)
        bbox_sampler = PseudoSampler()
        sampling_result = bbox_sampler.sample(assign_result, proposals,
                                              gt_bboxes)

    num_valid_proposals = proposals.shape[0]
    box_cn = gt_bboxes.shape[1]
    bbox_gt = proposals.new_zeros([num_valid_proposals, box_cn])
    pos_proposals = torch.zeros_like(proposals)
    proposals_weights = proposals.new_zeros([num_valid_proposals, box_cn])
    labels = proposals.new_zeros(num_valid_proposals, dtype=torch.long)
    label_weights = proposals.new_zeros(num_valid_proposals, dtype=torch.float)

    pos_inds = sampling_result.pos_inds
    neg_inds = sampling_result.neg_inds
    if len(pos_inds) > 0:
        pos_gt_bboxes = sampling_result.pos_gt_bboxes
        bbox_gt[pos_inds, :] = pos_gt_bboxes
        pos_proposals[pos_inds, :] = proposals[pos_inds, :]
        proposals_weights[pos_inds, :] = 1.0
        if gt_labels is None:
            labels[pos_inds] = 1
        else:
            labels[pos_inds] = gt_labels[sampling_result.pos_assigned_gt_inds]
        if cfg.pos_weight <= 0:
            label_weights[pos_inds] = 1.0
        else:
            label_weights[pos_inds] = cfg.pos_weight
    if len(neg_inds) > 0:
        label_weights[neg_inds] = 1.0

    # map up to original set of proposals
    if unmap_outputs:
        num_total_proposals = flat_proposals.size(0)
        labels = unmap(labels, num_total_proposals, inside_flags)
        label_weights = unmap(label_weights, num_total_proposals, inside_flags)
        bbox_gt = unmap(bbox_gt, num_total_proposals, inside_flags)
        pos_proposals = unmap(pos_proposals, num_total_proposals, inside_flags)
        proposals_weights = unmap(proposals_weights, num_total_proposals,
                                  inside_flags)

    return (labels, label_weights, bbox_gt, pos_proposals, proposals_weights,
            pos_inds, neg_inds)


def unmap(data, count, inds, fill=0):
    """ Unmap a subset of item (data) back to the original set of items (of
    size count) """
    if data.dim() == 1:
        ret = data.new_full((count, ), fill)
        ret[inds] = data
    else:
        new_size = (count, ) + data.size()[1:]
        ret = data.new_full(new_size, fill)
        ret[inds, :] = data
    return ret

def show_point_targets(pos_inds_list, all_proposals, gt_bboxes_list, flag):
  from mmdet.debug_tools import show_lines
  from configs.common import IMAGE_SIZE
  for (pos_inds, proposals, bbox_gt) in zip(pos_inds_list, all_proposals, gt_bboxes_list):
    proposals = proposals[pos_inds].cpu().data.numpy()
    bbox_gt = bbox_gt.cpu().data.numpy()
    if proposals.shape[1] == 3:
      points = proposals[:,:2]
    if proposals.shape[1] == 5:
      points = (proposals[:,0:2] + proposals[:,2:4])/2
      show_lines(bbox_gt, (IMAGE_SIZE, IMAGE_SIZE), lines_ref=proposals, name=flag+'_lines.png')
    show_lines(bbox_gt, (IMAGE_SIZE, IMAGE_SIZE), points=points, name=flag+'_centroids.png')
    pass



