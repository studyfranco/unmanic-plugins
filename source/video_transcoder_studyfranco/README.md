# Transcode Video Files
Plugin for [Unmanic](https://github.com/Unmanic)

---

### Information:

- [Description](description.md)
- [Changelog](changelog.md)

## Overview

This plugin allows you to transcode the video streams within your media files using various encoders. It provides flexibility in choosing codecs, quality settings, and hardware acceleration where available.

## Supported Encoders and Features

This plugin supports a range of video encoders. Below are some of the key encoders and their configurable options:

### libx264 & libx265 (CPU Encoding)
- **Preset:** Controls the encoding speed vs. compression efficiency. Slower presets offer better compression.
- **Tune:** Optimizes encoding for specific content types (e.g., film, animation).
- **Profile:** Sets the H.264/H.265 profile. 'auto' is generally recommended.
- **CRF (Constant Rate Factor):** Controls the quality. Lower values mean higher quality and larger files.
- **Average Bitrate:** Alternative rate control method for targeting a specific bitrate.

### QSV (Intel Quick Sync Video)
- Hardware-accelerated H.264 and HEVC encoding on supported Intel CPUs.
- Options for preset, quality, and bitrate control.

### VAAPI (Video Acceleration API)
- Hardware-accelerated encoding for AMD and Intel GPUs on Linux.
- Supports H.264 and HEVC.
- Options for quality and bitrate control.

### NVENC (NVIDIA Encoder)
- Hardware-accelerated H.264 and HEVC encoding on NVIDIA GPUs.
- Options for preset, quality, rate control, and other GPU-specific features.

### AV1 (libsvt-av1) Encoding
This plugin now includes support for AV1 encoding using the SVT-AV1 (Scalable Video Technology for AV1) encoder. AV1 offers superior compression efficiency compared to older codecs like H.264 and HEVC, meaning you can achieve similar quality at smaller file sizes, or higher quality at similar file sizes.

**Configurable Options for libsvt-av1:**

*   **Preset:** Controls the trade-off between encoding speed and compression efficiency.
    *   Ranges from `12` (fastest, lower quality) to `4` (slowest, best quality).
    *   `8` is the default.
*   **CRF (Constant Rate Factor):** Adjusts the output quality.
    *   Similar to x264/x265, lower values generally result in higher quality and larger files. A common starting point is `30`.
*   **Pixel Format (pix_fmt):** Specifies the pixel format for the output video (e.g., `yuv420p`, `yuv420p10le` for 10-bit).
    *   Leave empty to use the source pixel format. `yuv420p10le` is a common choice for 10-bit AV1.
*   **Scene Change Detection (scd):** Enables or disables scene change detection.
    *   `Enable` (default) can improve quality by allocating more bits to complex scenes.
    *   `Disable` might be useful in specific scenarios or for faster encoding.
*   **Custom Parameters:** Allows you to pass additional command-line parameters directly to the libsvt-av1 encoder.
    *   Useful for advanced tuning, e.g., `-svtav1-params tune=0`. Refer to the SVT-AV1 documentation for available parameters.

## Configuration
The plugin settings can be accessed through the Unmanic UI. You can select your desired video encoder and configure its specific options based on your needs.

**Basic Mode:** Simplifies configuration by providing pre-defined quality settings.
**Standard Mode:** Offers more granular control over encoder parameters.

Ensure your FFmpeg build includes the encoders you wish to use (especially libsvt-av1).
