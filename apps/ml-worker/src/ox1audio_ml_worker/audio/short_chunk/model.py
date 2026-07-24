"""Short-chunk CNN + Residual (vendored, MIT).

Adapted from minzwon/sota-music-tagging-models training/model.py + modules.py.
Only Res_2d and ShortChunkCNN_Res are retained.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torchaudio


class Res_2d(nn.Module):
    def __init__(self, input_channels: int, output_channels: int, shape: int = 3, stride: int = 2):
        super().__init__()
        self.conv_1 = nn.Conv2d(
            input_channels, output_channels, shape, stride=stride, padding=shape // 2
        )
        self.bn_1 = nn.BatchNorm2d(output_channels)
        self.conv_2 = nn.Conv2d(output_channels, output_channels, shape, padding=shape // 2)
        self.bn_2 = nn.BatchNorm2d(output_channels)

        self.diff = False
        if (stride != 1) or (input_channels != output_channels):
            self.conv_3 = nn.Conv2d(
                input_channels, output_channels, shape, stride=stride, padding=shape // 2
            )
            self.bn_3 = nn.BatchNorm2d(output_channels)
            self.diff = True
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.bn_2(self.conv_2(self.relu(self.bn_1(self.conv_1(x)))))
        if self.diff:
            x = self.bn_3(self.conv_3(x))
        out = x + out
        return self.relu(out)


class ShortChunkCNN_Res(nn.Module):
    """Short-chunk CNN with residual connections (3.69 s / 16 kHz mel input)."""

    def __init__(
        self,
        n_channels: int = 128,
        sample_rate: int = 16000,
        n_fft: int = 512,
        f_min: float = 0.0,
        f_max: float = 8000.0,
        n_mels: int = 128,
        n_class: int = 50,
    ):
        super().__init__()

        self.spec = torchaudio.transforms.MelSpectrogram(
            sample_rate=sample_rate,
            n_fft=n_fft,
            f_min=f_min,
            f_max=f_max,
            n_mels=n_mels,
        )
        self.to_db = torchaudio.transforms.AmplitudeToDB()
        self.spec_bn = nn.BatchNorm2d(1)

        self.layer1 = Res_2d(1, n_channels, stride=2)
        self.layer2 = Res_2d(n_channels, n_channels, stride=2)
        self.layer3 = Res_2d(n_channels, n_channels * 2, stride=2)
        self.layer4 = Res_2d(n_channels * 2, n_channels * 2, stride=2)
        self.layer5 = Res_2d(n_channels * 2, n_channels * 2, stride=2)
        self.layer6 = Res_2d(n_channels * 2, n_channels * 2, stride=2)
        self.layer7 = Res_2d(n_channels * 2, n_channels * 4, stride=2)

        self.dense1 = nn.Linear(n_channels * 4, n_channels * 4)
        self.bn = nn.BatchNorm1d(n_channels * 4)
        self.dense2 = nn.Linear(n_channels * 4, n_class)
        self.dropout = nn.Dropout(0.5)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.spec(x)
        x = self.to_db(x)
        x = x.unsqueeze(1)
        x = self.spec_bn(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.layer5(x)
        x = self.layer6(x)
        x = self.layer7(x)
        x = x.squeeze(2)

        if x.size(-1) != 1:
            x = nn.MaxPool1d(x.size(-1))(x)
        x = x.squeeze(2)

        x = self.dense1(x)
        x = self.bn(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.dense2(x)
        return torch.sigmoid(x)
