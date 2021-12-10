# Copyright (C) 2021, Mindee.

# This program is licensed under the Apache License version 2.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0.txt> for full license details.

import os

os.environ['USE_TORCH'] = '1'

import datetime
import logging
import multiprocessing as mp
import time

import numpy as np
import torch
import torch.optim as optim
import wandb
from fastprogress.fastprogress import master_bar, progress_bar
from torch.utils.data import DataLoader, RandomSampler, SequentialSampler

from doctr import transforms as T
from doctr.datasets import DocArtefacts
from doctr.models import obj_detection
from doctr.utils import DetectionMetric


def convert_to_abs_coords(targets, img_shape):
    height, width = img_shape[-2:]

    for idx, t in enumerate(targets):
        targets[idx]['boxes'][:, 0::2] = (t['boxes'][:, 0::2] * width).round()
        targets[idx]['boxes'][:, 1::2] = (t['boxes'][:, 1::2] * height).round()

    targets = [{
        "boxes": torch.from_numpy(t['boxes']).to(dtype=torch.float32),
        "labels": torch.tensor(t['labels']).to(dtype=torch.long)}
        for t in targets
    ]

    return targets


def fit_one_epoch(model, train_loader, optimizer, scheduler, mb, amp=False):

    if amp:
        scaler = torch.cuda.amp.GradScaler()

    model.train()
    train_iter = iter(train_loader)
    # Iterate over the batches of the dataset
    for images, targets in progress_bar(train_iter, parent=mb):

        targets = convert_to_abs_coords(targets, images.shape)
        if torch.cuda.is_available():
            images = images.cuda()
            targets = [{k: v.cuda() for k, v in t.items()} for t in targets]

        optimizer.zero_grad()
        if amp:
            with torch.cuda.amp.autocast():
                loss_dict = model(images, targets)
                loss = sum(v for v in loss_dict.values())
            scaler.scale(loss).backward()
            # Update the params
            scaler.step(optimizer)
            scaler.update()
        else:
            loss_dict = model(images, targets)
            loss = sum(v for v in loss_dict.values())
            loss.backward()
            optimizer.step()

        mb.child.comment = f'Training loss: {loss.item()}'
    scheduler.step()


@torch.no_grad()
def evaluate(model, val_loader, metric, amp=False):
    model.eval()
    metric.reset()
    val_iter = iter(val_loader)
    for images, targets in val_iter:

        images, targets = next(val_iter)
        targets = convert_to_abs_coords(targets, images.shape)
        if torch.cuda.is_available():
            images = images.cuda()

        if amp:
            with torch.cuda.amp.autocast():
                output = model(images)
        else:
            output = model(images)

        # Compute metric
        pred_labels = np.concatenate([o['labels'].cpu().numpy() for o in output])
        pred_boxes = np.concatenate([o['boxes'].cpu().numpy() for o in output])
        gt_boxes = np.concatenate([o['boxes'].cpu().numpy() for o in targets])
        gt_labels = np.concatenate([o['labels'].cpu().numpy() for o in targets])
        metric.update(gt_boxes, pred_boxes, gt_labels, pred_labels)

    return metric.summary()


def main(args):

    print(args)

    if not isinstance(args.workers, int):
        args.workers = min(16, mp.cpu_count())

    torch.backends.cudnn.benchmark = True

    st = time.time()
    val_set = DocArtefacts(
        train=False,
        download=True,
        sample_transforms=T.Resize((args.input_size, args.input_size)),
    )
    val_loader = DataLoader(
        val_set,
        batch_size=args.batch_size,
        drop_last=False,
        num_workers=args.workers,
        sampler=SequentialSampler(val_set),
        pin_memory=torch.cuda.is_available(),
        collate_fn=val_set.collate_fn,
    )
    print(f"Validation set loaded in {time.time() - st:.4}s ({len(val_set)} samples in "
          f"{len(val_loader)} batches)")

    # Load doctr model
    model = obj_detection.__dict__[args.arch](pretrained=args.pretrained, num_classes=5)

    # Resume weights
    if isinstance(args.resume, str):
        print(f"Resuming {args.resume}")
        checkpoint = torch.load(args.resume, map_location='cpu')
        model.load_state_dict(checkpoint)

    # GPU
    if isinstance(args.device, int):
        if not torch.cuda.is_available():
            raise AssertionError("PyTorch cannot access your GPU. Please investigate!")
        if args.device >= torch.cuda.device_count():
            raise ValueError("Invalid device index")
    # Silent default switch to GPU if available
    elif torch.cuda.is_available():
        args.device = 0
    else:
        logging.warning("No accessible GPU, target device set to CPU.")
    if torch.cuda.is_available():
        torch.cuda.set_device(args.device)
        model = model.cuda()

    # Metrics
    metric = DetectionMetric(iou_thresh=0.5)

    if args.test_only:
        print("Running evaluation")
        recall, precision, mean_iou = evaluate(model, val_loader, metric, amp=args.amp)
        print(f"Recall: {recall:.2%} | Precision: {precision:.2%} |IoU: {mean_iou:.2%}")
        return

    st = time.time()
    # Load both train and val data generators
    train_set = DocArtefacts(
        train=True,
        download=True,
        sample_transforms=T.Resize((args.input_size, args.input_size)),
    )

    train_loader = DataLoader(
        train_set,
        batch_size=args.batch_size,
        drop_last=True,
        num_workers=args.workers,
        sampler=RandomSampler(train_set),
        pin_memory=torch.cuda.is_available(),
        collate_fn=train_set.collate_fn,
    )
    print(f"Train set loaded in {time.time() - st:.4}s ({len(train_set)} samples in "
          f"{len(train_loader)} batches)")

    # Backbone freezing
    if args.freeze_backbone:
        for p in model.backbone.parameters():
            p.reguires_grad_(False)

    # Optimizer
    optimizer = optim.SGD([p for p in model.parameters() if p.requires_grad],
                          lr=args.lr, weight_decay=args.weight_decay)
    # Scheduler
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=8, gamma=0.7)

    # Training monitoring
    current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    exp_name = f"{args.arch}_{current_time}" if args.name is None else args.name

    # W&B
    if args.wb:

        run = wandb.init(
            name=exp_name,
            project="object-detection",
            config={
                "learning_rate": args.lr,
                "epochs": args.epochs,
                "weight_decay": args.weight_decay,
                "batch_size": args.batch_size,
                "architecture": args.arch,
                "input_size": args.input_size,
                "optimizer": "sgd",
                "framework": "pytorch",
                "scheduler": args.sched,
                "pretrained": args.pretrained,
                "amp": args.amp,
            }
        )

    mb = master_bar(range(args.epochs))
    max_score = 0.

    for epoch in mb:
        fit_one_epoch(model, train_loader, optimizer, scheduler, mb, amp=args.amp)
        # Validation loop at the end of each epoch
        recall, precision, mean_iou = evaluate(model, val_loader, metric, amp=args.amp)
        f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.

        if f1_score > max_score:
            print(f"Validation metric increased {max_score:.6} --> {f1_score:.6}: saving state...")
            torch.save(model.state_dict(), f"./{exp_name}.pt")
            max_score = f1_score
        log_msg = f"Epoch {epoch + 1}/{args.epochs} - "
        if any(val is None for val in (recall, precision, mean_iou)):
            log_msg += "Undefined metric value, caused by empty GTs or predictions"
        else:
            log_msg += f"Recall: {recall:.2%} | Precision: {precision:.2%} | Mean IoU: {mean_iou:.2%}"
        mb.write(log_msg)
        # W&B
        if args.wb:
            wandb.log({
                'recall': recall,
                'precision': precision,
                'iou': mean_iou,
            })

    if args.wb:
        run.finish()


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description='DocTR training script for object detection (PyTorch)',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('arch', type=str, help='text-detection model to train')
    parser.add_argument('--name', type=str, default=None, help='Name of your training experiment')
    parser.add_argument('--epochs', type=int, default=10, help='number of epochs to train the model on')
    parser.add_argument('-b', '--batch_size', type=int, default=2, help='batch size for training')
    parser.add_argument('--device', default=None, type=int, help='device')
    parser.add_argument('--input_size', type=int, default=1024, help='model input size, H = W')
    parser.add_argument('--lr', type=float, default=0.001, help='learning rate for the optimizer (SGD)')
    parser.add_argument('--wd', '--weight-decay', default=0, type=float, help='weight decay', dest='weight_decay')
    parser.add_argument('-j', '--workers', type=int, default=None, help='number of workers used for dataloading')
    parser.add_argument('--resume', type=str, default=None, help='Path to your checkpoint')
    parser.add_argument("--test-only", dest='test_only', action='store_true', help="Run the validation loop")
    parser.add_argument('--freeze-backbone', dest='freeze_backbone', action='store_true',
                        help='freeze model backbone for fine-tuning')
    parser.add_argument('--wb', dest='wb', action='store_true',
                        help='Log to Weights & Biases')
    parser.add_argument('--pretrained', dest='pretrained', action='store_true',
                        help='Load pretrained parameters before starting the training')
    parser.add_argument("--amp", dest="amp", help="Use Automatic Mixed Precision", action="store_true")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    main(args)
