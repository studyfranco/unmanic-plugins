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

**Configurable Options for libsvt-av1 (Basic and Standard Modes):**

*   **Preset:** Controls the trade-off between encoding speed and compression efficiency.
    *   Ranges from `12` (fastest, lower quality) to `1` (slowest, best quality, e.g. `4` in previous version). Default is `4`.
*   **CRF (Constant Rate Factor):** Adjusts the output quality.
    *   Similar to x264/x265, lower values generally result in higher quality and larger files. A common starting point is `23` for libsvtav1.

## SVT-AV1 Encoder Settings (Advanced Mode)

When "Advanced" mode is selected in the plugin settings, the following granular parameters for the SVT-AV1 encoder (libsvtav1) become available:

-   **Preset**
    -   **UI Label:** Encoder quality preset
    -   **Corresponding FFmpeg Flag/Param:** `-preset` (top-level FFmpeg option)
    -   **Type:** Integer (String in UI, converted)
    -   **Default Value:** "4"
    -   **Description:** Controls the encoding speed vs. compression efficiency. Ranges from 1 (best quality, slowest) to 12 (fastest, lower quality).

-   **Constant Rate Factor (CRF)**
    -   **UI Label:** Constant rate factor
    -   **Corresponding FFmpeg Flag/Param:** `-crf` (top-level FFmpeg option)
    -   **Type:** Integer (String in UI, converted)
    -   **Default Value:** "23"
    -   **Description:** Adjusts the output quality. Lower values mean higher quality and larger files. Valid range typically 0-51 or 0-63.

-   **GOP Size (-g)**
    -   **UI Label:** GOP Size (-g)
    -   **Corresponding FFmpeg Flag/Param:** `-g` (top-level FFmpeg option)
    -   **Type:** Integer
    -   **Default Value:** 240
    -   **Description:** Sets the Group of Pictures size. Must be >= 1.

-   **Scene Change Detection (-sc_detection)**
    -   **UI Label:** Scene Change Detection (-sc_detection)
    -   **Corresponding FFmpeg Flag/Param:** `-sc_detection` (top-level FFmpeg option)
    -   **Type:** Integer (0 or 1)
    -   **Default Value:** 1 (Enabled)
    -   **Description:** FFmpeg top-level scene change detection. 0 = Disable, 1 = Enable.

-   **SVT-AV1: Scene Change Detection (scd)**
    -   **UI Label:** SVT-AV1: Scene Change Detection (scd)
    -   **Corresponding FFmpeg Flag/Param:** `scd` (within `-svtav1-params`)
    -   **Type:** Integer (0 or 1)
    -   **Default Value:** 1 (Enabled)
    -   **Description:** Scene change detection specifically for libsvtav1. 0 = Disable, 1 = Enable.

-   **SVT-AV1: Enable Overlays (enable-overlays)**
    -   **UI Label:** SVT-AV1: Enable Overlays (enable-overlays)
    -   **Corresponding FFmpeg Flag/Param:** `enable-overlays` (within `-svtav1-params`)
    -   **Type:** Integer (0 or 1)
    -   **Default Value:** 1 (Enabled)
    -   **Description:** Enable overlay frames for improved quality on content with overlays.

-   **SVT-AV1: Tune (tune)**
    -   **UI Label:** SVT-AV1: Tune (tune)
    -   **Corresponding FFmpeg Flag/Param:** `tune` (within `-svtav1-params`)
    -   **Type:** Integer
    -   **Default Value:** 2 (SSIM)
    -   **Description:** Tune the encoder for a specific metric. 0 = Visual Quality (VQ), 1 = PSNR (Objective Quality), 2 = SSIM (Objective Quality).

-   **SVT-AV1: Adaptive Quantization Mode (aq-mode)**
    -   **UI Label:** SVT-AV1: Adaptive Quantization Mode (aq-mode)
    -   **Corresponding FFmpeg Flag/Param:** `aq-mode` (within `-svtav1-params`)
    -   **Type:** Integer
    -   **Default Value:** 2 (Complexity AQ)
    -   **Description:** Sets the Adaptive Quantization mode (0-4). 0=Off, 1=Variance AQ, 2=Complexity AQ, 3=Cyclic Refresh AQ, 4=Delta QP based AQ.

-   **SVT-AV1: Enable CDEF (enable-cdef)**
    -   **UI Label:** SVT-AV1: Enable CDEF (enable-cdef)
    -   **Corresponding FFmpeg Flag/Param:** `enable-cdef` (within `-svtav1-params`)
    -   **Type:** Boolean (1 for True, 0 for False)
    -   **Default Value:** True (Enabled)
    -   **Description:** Enables the Constrained Directional Enhancement Filter.

-   **SVT-AV1: Enable Restoration (enable-restoration)**
    -   **UI Label:** SVT-AV1: Enable Restoration (enable-restoration)
    -   **Corresponding FFmpeg Flag/Param:** `enable-restoration` (within `-svtav1-params`)
    -   **Type:** Boolean (1 for True, 0 for False)
    -   **Default Value:** True (Enabled)
    -   **Description:** Enables the Loop Restoration Filter.

-   **SVT-AV1: Enable QM (enable-qm)**
    -   **UI Label:** SVT-AV1: Enable QM (enable-qm)
    -   **Corresponding FFmpeg Flag/Param:** `enable-qm` (within `-svtav1-params`)
    -   **Type:** Boolean (1 for True, 0 for False)
    -   **Default Value:** True (Enabled)
    -   **Description:** Enables Quantization Matrix.

-   **SVT-AV1: Enable Variance Boost (enable-variance-boost)**
    -   **UI Label:** SVT-AV1: Enable Variance Boost (enable-variance-boost)
    -   **Corresponding FFmpeg Flag/Param:** `enable-variance-boost` (within `-svtav1-params`)
    -   **Type:** Boolean (1 for True, 0 for False)
    -   **Default Value:** True (Enabled)
    -   **Description:** Enables variance boost for better subjective quality.

-   **SVT-AV1: Additional Parameters (svtav1_additional_params)**
    -   **UI Label:** SVT-AV1: Additional Parameters
    -   **Corresponding FFmpeg Flag/Param:** Appended to `-svtav1-params` string
    -   **Type:** String
    -   **Default Value:** "" (empty)
    -   **Description:** Allows specifying other SVT-AV1 parameters as a colon-separated string (e.g., `key1=value1:key2=value2`). Refer to SVT-AV1 documentation for all available parameters.

## Configuration
The plugin settings can be accessed through the Unmanic UI. You can select your desired video encoder and configure its specific options based on your needs.

**Basic Mode:** Simplifies configuration by providing pre-defined quality settings.
**Standard Mode:** Offers more granular control over encoder parameters.
**Advanced Mode:** Provides access to detailed encoder-specific parameters, such as the SVT-AV1 settings listed above.

Ensure your FFmpeg build includes the encoders you wish to use (especially libsvt-av1).
