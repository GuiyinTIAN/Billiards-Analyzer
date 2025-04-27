# import torch

# model = torch.load(r"runs\train\RedBlueWhite\weights\best.pt", map_location="cpu")  # 先加载
# torch.save(model.state_dict(), r"macRedBlueWhite.pt")  # 重新保存为纯权重

import torch

# 加载检查点
checkpoint = torch.load("/Users/hejunhao/Desktop/Study/ELEC 4544/GroupProject/NineBallPocketNoNine/weights/best.pt", map_location="cpu")

if 'opt' in checkpoint:
    del checkpoint['opt']

# 保存修改后的 checkpoint（可选）
torch.save(checkpoint, "macNineBallPocketNoNine.pt")