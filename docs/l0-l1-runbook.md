# L0 / L1 运行与验收说明

本文面向本地 Windows PowerShell 工作流。项目根目录示例：`F:\\python\\aiMontage`。

## 层级边界

### L0 — 不可变媒体事实与来源追溯

目的：为后续分析建立可重复核对的输入基线。视频 SHA-256 是源文件身份；源帧时间戳 `source_pts_time` 是时间轴权威值；解码器时间戳只作诊断。保留原始上游输出与 aiMontage 归一化证据，帧关联使用 `(source_sha256, frame_no)`，不能只依赖文件名。

当前实现分布在 `scripts/run_real_video_e2e.py`、`src/aimontage/evidence.py`、`src/aimontage/timestamp_audit.py`。它会运行固定版本的 OpenMontage 上游工具，并产出 `evidence_bundle.json`，其中包括源文件信息、时间戳审计、归一化镜头区间、抽样帧映射和证据记录。当前尚没有独立的 `l0_media_facts.py` 单文件入口；L0 能力由这个端到端脚本及公共证据模块共同实现。

### L1 — 镜头、帧与视觉变化证据

目的：形成供人或多模态模型审查的视觉证据，不直接下剧情结论。

- 镜头与常规抽帧：由 `run_real_video_e2e.py` 调用固定版本的上游 `scene_detect`、`frame_sampler`。
- 密集抽帧：`run_dense_frame_sampling.py` 按时间间隔抽帧，默认推荐 0.25 秒；每帧保留源 SHA、源帧号、源 PTS、相对路径和图像 SHA。
- 运动候选：`analyze_motion_dense_frames.py` 对相邻密集帧计算 Farneback 光流强度。它输出变化强度候选，不提供可靠的物体运动方向，也不能单独区分主体运动与摄像机运动。
- 人工复核：`build_motion_review_sheet.py` 生成按时间顺序排列的运动候选 HTML。它是候选审查表，不是剧情脚本。

## 环境准备

在仓库根目录运行：

```powershell
Set-Location "F:\\python\\aiMontage"
$env:PYTHONPATH = (Join-Path (Get-Location).Path "src")
python --version
ffmpeg -version
ffprobe -version
```

需要已安装 FFmpeg/ffprobe、Python 依赖（至少 OpenCV 与 NumPy），并已初始化 `vendor/OpenMontage` 子模块。若子模块尚未初始化：

```powershell
git submodule update --init --recursive
```

## 执行命令

### 1. L0 + 常规 L1：镜头与基础证据包

```powershell
python scripts/run_real_video_e2e.py --video ".\\a.mp4" --out ".\\artifacts\\real_video_e2e" --repo-root ".\\vendor\\OpenMontage"
```

成功时应输出 `status: passed`，并生成：

- `artifacts/real_video_e2e/evidence_bundle.json`
- 上游原始输出和归一化的镜头、抽样帧证据（具体文件以运行结果为准）

该脚本默认输入 `a.mp4`、输出 `artifacts/real_video_e2e`，但显式传参更适合复现。

### 2. L1：0.25 秒密集抽帧

```powershell
python scripts/run_dense_frame_sampling.py --video ".\\a.mp4" --out ".\\artifacts\\real_video_e2e\\dense_frames" --interval-seconds 0.25
```

预期文件：`artifacts/real_video_e2e/dense_frames/dense_frame_evidence.json` 及其 `frames/` 图片目录。样本数随视频时长、时间戳和抽帧实现变化，不应硬编码为固定值。

### 3. L1：运动强度候选

```powershell
python scripts/analyze_motion_dense_frames.py --evidence ".\\artifacts\\real_video_e2e\\dense_frames\\dense_frame_evidence.json" --out ".\\artifacts\\real_video_e2e\\motion_dense_review.json"
```

注意：这个脚本只接受 `--evidence` 和 `--out`，不传 `--video`。

### 4. L1：运动候选人工复核页

```powershell
python scripts/build_motion_review_sheet.py --evidence ".\\artifacts\\real_video_e2e\\dense_frames\\dense_frame_evidence.json" --motion-report ".\\artifacts\\real_video_e2e\\motion_dense_review.json" --out ".\\artifacts\\real_video_e2e\\motion_review_sheet.html"
Start-Process (Resolve-Path ".\\artifacts\\real_video_e2e\\motion_review_sheet.html").Path
```

### 5. L1：全视频按时间顺序联系表（剧情理解的视觉入口）

```powershell
python scripts/build_chronological_contact_sheet.py --evidence ".\\artifacts\\real_video_e2e\\dense_frames\\dense_frame_evidence.json" --out ".\\artifacts\\real_video_e2e\\chronological_contact_sheet.html"
Start-Process (Resolve-Path ".\\artifacts\\real_video_e2e\\chronological_contact_sheet.html").Path
```

联系表按 `source_pts_time` 升序展示所有密集帧，并显示样本编号、时间戳、源帧号。它帮助快速浏览整体剧情，不替代原视频播放，也不保证捕捉每一个短暂动作。

## 推荐完整执行顺序

1. 运行 L0 + 常规 L1，检查 `evidence_bundle.json` 与状态。
2. 运行密集抽帧。
3. 运行光流候选。
4. 打开全时间线联系表，先理解故事全貌。
5. 打开运动候选复核表，检查高变化区间。
6. 在后续 L2 剧情理解中，把每个结论关联到时间戳/证据帧；将观察事实、推断和未确认项分开。

## 当前已知验收记录（本地 `a.mp4`）

截至 2026-10-24，用户本地已实际运行并确认：

- 密集抽帧成功，49 帧，间隔 0.25 秒。
- 光流分析处理 48 个相邻区间，输出 12 个运动候选。
- 运动候选 HTML 已重新生成，候选时间顺序经人工确认正确。
- 清晰度报告尚待执行/确认。
- 全视频联系表是本次新增的下一步，必须在本地实际运行后再记录验收结果。

## 限制

- L0/L1 输出是证据，不是完整的语义理解。
- 光流强度不等于物体速度或运动方向；摄像机运动、剪辑、闪光、压缩噪声也可能成为候选。
- 0.25 秒抽样可能漏掉更短动作。发现关键事件时应回到源视频补充帧或逐帧检查。
- 不要在 L2 之前把候选区间直接写成已确认剧情。

## 快速复用 OpenMontage 原生视频分析（推荐下一步）

在 L0/L1 证据工具之外，aiMontage 增加了一个薄适配入口，直接调用固定提交中的
`tools.analysis.video_analyzer.VideoAnalyzer`。不复制上游代码，不改写官方
`video_analysis_brief` 字段；aiMontage 只另外生成运行清单并检查必要结构。

先确保子模块已初始化，然后在仓库根目录运行：

```powershell
Set-Location "F:\\python\\aiMontage"
$env:PYTHONPATH = (Join-Path (Get-Location).Path "src")
python scripts/run_openmontage_video_analyzer.py --video ".\\a.mp4" --out ".\\artifacts\\openmontage_video_analysis" --repo-root ".\\vendor\\OpenMontage" --depth standard --max-keyframes 20
```

输出：
- `artifacts/openmontage_video_analysis/video_analysis_brief.json`：OpenMontage 原生分析结果，保持上游字段。
- `artifacts/openmontage_video_analysis/analysis_run_manifest.json`：源视频 SHA-256、上游固定版本、场景/关键帧数量、工具步骤和结构校验状态。

`--depth standard` 先作为快速基线；确认效果后再用 `--depth deep` 增加场景内采样。
`video_analyzer` 中的场景描述字段可能为空，这是预期行为：工具负责结构化提取，语义解释仍需查看关键帧并进行证据化复核。脚本返回 `review_required` 时不要把结果直接当成可渲染 Blueprint。

注意：本入口已提交到仓库，但尚未在用户的 Windows 环境中执行验收。首次运行若失败，先看终端中 OpenMontage 子模块路径和依赖错误；不要通过复制上游源码来绕过问题。


## OpenMontage scene candidates → L2 event draft

After `scripts/run_openmontage_video_analyzer.py` has produced its official brief and
run manifest, create a reviewable event draft:

```powershell
python scripts/build_openmontage_event_draft.py `
  --brief artifacts/openmontage_video_analysis/video_analysis_brief.json `
  --manifest artifacts/openmontage_video_analysis/analysis_run_manifest.json `
  --out artifacts/openmontage_video_analysis/l2_event_draft.json
```

The adapter writes `aimontage.l2_event_timeline.v2`. It preserves each complete upstream
scene object (including fields such as `visual_type`, `energy_level`, `motion_type`, and
`flow_variance`), the global `content_analysis` summary/topics/audience, and references
to upstream keyframes. It adds JSON-pointer evidence references and does not mutate the
official brief. Empty scene descriptions remain empty; global summary text is not copied
into individual scene events. Verified timing/frame fields remain null until timestamp-audited
frame mapping and semantic review exist. A duration overrun within 0.0001 seconds is
reported as a precision-tolerance warning; larger overruns are surfaced as normal warnings.
The output is a richer analysis/evidence draft, not an approval to render. The next pipeline
step should consume its preserved analysis and keyframe references instead of asking users
to re-enter information already generated by OpenMontage.
