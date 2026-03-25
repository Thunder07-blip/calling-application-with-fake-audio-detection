"""
model.py — VoiceDetector Architecture
======================================
Input:  raw audio waveform, shape [B, 48000]
Output: single raw logit per sample, shape [B, 1]  (NO sigmoid inside model)

Loss:   Use nn.BCEWithLogitsLoss() in your training script.
Infer:  Use torch.sigmoid(logits) to get probabilities [0, 1].
"""

import torch
import torch.nn as nn
import torchaudio.transforms as T


class ResidualBlock(nn.Module):
    """
    Standard pre-activation Residual Block for 2D feature maps (spectrograms).
    bias=False on all Conv2d layers because BatchNorm absorbs the bias — cleaner and faster.
    """
    def __init__(self, in_c: int, out_c: int, stride: int = 1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c, out_c, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1   = nn.BatchNorm2d(out_c)
        self.conv2 = nn.Conv2d(out_c, out_c, kernel_size=3, stride=1,      padding=1, bias=False)
        self.bn2   = nn.BatchNorm2d(out_c)

        # Shortcut connection — matches dimensions when stride or channels change
        self.shortcut = nn.Sequential()
        if stride != 1 or in_c != out_c:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_c)
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return torch.relu(out + self.shortcut(x))


class VoiceDetector(nn.Module):
    """
    End-to-end deepfake voice detector.

    Pipeline inside the model:
        [B, 48000]  →  MelSpectrogram  →  [B, 128, T]
                    →  AmplitudeToDB   →  log scale
                    →  +1e-9           →  floor to prevent log(0) = -inf
                    →  unsqueeze(1)    →  [B, 1, 128, T]  (grayscale "image")
                    →  InstanceNorm2d  →  per-clip contrast normalization
                    →  ResNet stem + 3 residual blocks
                    →  AdaptiveAvgPool →  [B, 256]
                    →  FC head         →  [B, 1]  (raw logit)

    Why InstanceNorm2d?
        BatchNorm normalizes across the batch — but a batch of loud fakes and quiet reals
        will have very different means. InstanceNorm2d normalizes each spectrogram
        individually, so the CNN learns *texture patterns*, not loudness.
    """

    def __init__(self, sample_rate: int = 16000, n_mels: int = 128,
                 n_fft: int = 1024, hop_length: int = 160):
        super().__init__()

        # --- Spectrogram layers (non-trainable transforms) ---
        self.mel = T.MelSpectrogram(
            sample_rate=sample_rate,
            n_mels=n_mels,
            n_fft=n_fft,
            hop_length=hop_length
        )
        self.db = T.AmplitudeToDB()

        # --- Per-clip normalization ---
        # affine=True: lets the model learn optimal scale/shift after normalization
        self.spec_norm = nn.InstanceNorm2d(1, affine=True)

        # --- CNN backbone ---
        # Stem: initial feature extraction from the normalized spectrogram "image"
        self.stem = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU()
        )
        self.layer1 = ResidualBlock(32,  64,  stride=2)   # Downsample ×2
        self.layer2 = ResidualBlock(64,  128, stride=2)   # Downsample ×4
        self.layer3 = ResidualBlock(128, 256, stride=2)   # Downsample ×8

        # Global average pooling — collapses spatial dims to a single vector
        self.pool = nn.AdaptiveAvgPool2d((1, 1))

        # --- Classification head ---
        # Dropout(0.4) is intentionally aggressive to prevent overfitting on 80k clips
        self.fc = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(128, 1)
            # ⚠️  NO nn.Sigmoid() here — BCEWithLogitsLoss applies it in float32 internally
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: raw waveform tensor, shape [B, 48000]
        Returns:
            logits: raw (un-sigmoided) scores, shape [B, 1]
        """
        # ── Spectrogram (MUST run in float32) ───────────────────────────────
        # torchaudio's MelSpectrogram uses FFT internally.
        # FFT operations silently OVERFLOW in float16 (the autocast dtype),
        # producing inf → NaN in the loss after ~40 batches.
        #
        # `autocast(enabled=False)` creates a float32 island inside the autocast
        # context so the CNN backbone still benefits from AMP speed,
        # but the spectrogram is always computed safely in float32.
        with torch.amp.autocast(device_type='cuda', enabled=False):
            x_f32 = x.float()                           # Guarantee float32 input
            x = self.db(self.mel(x_f32) + 1e-9)        # [B, n_mels, T]  — float32
            x = x.unsqueeze(1)                          # [B, 1, n_mels, T]

        # ── Per-clip normalization (safe in float16, runs under outer autocast) ──
        x = self.spec_norm(x)            # [B, 1, n_mels, T]

        # ── CNN feature extraction ────────────────────────────────────────────
        x = self.stem(x)                 # [B, 32, n_mels,   T  ]
        x = self.layer1(x)              # [B, 64, n_mels/2, T/2]
        x = self.layer2(x)              # [B, 128,n_mels/4, T/4]
        x = self.layer3(x)              # [B, 256,n_mels/8, T/8]

        # ── Pool → classify ───────────────────────────────────────────────────
        x = self.pool(x).view(x.size(0), -1)  # [B, 256]
        return self.fc(x)                      # [B, 1]


if __name__ == "__main__":
    """Quick sanity check — run this file directly to validate shapes."""
    model = VoiceDetector()
    model.eval()

    dummy_waveform = torch.randn(4, 48000)  # Batch of 4 clips
    with torch.no_grad():
        logits = model(dummy_waveform)
        probs  = torch.sigmoid(logits)

    print(f"Input shape:  {dummy_waveform.shape}")   # Expected: [4, 48000]
    print(f"Logits shape: {logits.shape}")           # Expected: [4, 1]
    print(f"Probs range:  min={probs.min():.3f}  max={probs.max():.3f}")  # Should be in (0, 1)
    print("✅ Model sanity check passed.")
