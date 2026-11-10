---
id: cotton_weed_ai_pipeline
title: Cotton Weed Detection AI Computer Vision Pipeline
technologies:
  - YOLOv8
  - PyTorch
  - Python
  - OpenCV
  - Flask
  - React
  - OpenVINO
  - Docker
  - Docker Compose
domain: Computer Vision & Applied Machine Learning
status: completed
summary: End-to-end computer vision web application detecting weeds in cotton fields from UAV/drone footage with side-by-side video annotation and sub-5ms inference.
metrics: 0.8489 overall mAP@50 (93.8% mAP@50 cotton plants, 76.0% weed detection) at 3.1ms inference speed; 100% containerized deployment.
---

### Cotton Weed Detection AI Computer Vision Pipeline
*YOLOv8 | PyTorch | Python | OpenCV | Flask | React | Docker*

- Built and trained an end-to-end deep learning computer vision pipeline utilizing YOLOv8n to analyze high-resolution drone imagery for precision agriculture.
- Achieved 0.8489 mAP@50 overall with 93.8% mAP@50 for crop detection and 76.0% for weed detection at an ultra-low 3.1ms inference latency.
- Developed a full-stack web interface featuring a React frontend with side-by-side original vs. annotated video playback and a Flask REST backend.
- Accelerated real-time inference using Intel OpenVINO model optimization and built background frame extraction and video reassembly workers.
- Fully containerized the frontend, backend, and inference engine using Docker Compose for reproducible cross-platform deployment.

