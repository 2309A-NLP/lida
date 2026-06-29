# Agent工单3 - 文生图智能体

本项目围绕 `requirements.pdf` 的工单要求实现，当前正式方案已经切换为阿里云百炼在线图像编辑 API，不再依赖本机 Stable Diffusion 推理。

目标产出：
- 输入 1 张人脸原图
- 生成 3 张结果图：`front`、`left_turn`、`right_turn`
- 生成 1 张扩图结果：`outpaint`
- 输出结果清单、测试结果、实现步骤与过程问题记录

项目入口：
- 命令行入口：`run.py`
- Web 页面入口：`app.py`

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置百炼 API Key

Windows PowerShell:

```powershell
$env:DASHSCOPE_API_KEY="你的百炼API Key"
```

## 命令行运行

```bash
python run.py ^
  --input "D:\path\face.png" ^
  --output-dir ".\outputs" ^
  --subject-hint "young asian woman, natural skin tone" ^
  --seed 42
```

## Web UI 运行

```bash
python app.py
```

## 当前实现说明

- 预处理：OpenCV 检测主人脸并裁切到统一画幅
- 正脸、左转、右转：调用百炼 `description_edit`
- 扩图：调用百炼 `expand`
- 所有生成结果会自动保存到输出目录，并写入 `result_manifest.json`
