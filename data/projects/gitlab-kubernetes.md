---
id: gitlab_k8s_platform
title: Self-Hosted GitLab CI/CD Platform on Kubernetes
technologies:
  - Kubernetes
  - Minikube
  - Docker Compose
  - NGINX Ingress
  - Cert-Manager
  - TLS/SSL
  - PostgreSQL
  - Prometheus
  - Grafana
  - EFK Stack
  - Bash
domain: Cloud Infrastructure & DevOps
status: completed
summary: Complete, self-hosted, production-grade GitLab CI/CD platform orchestrated with Kubernetes and Docker Compose, featuring external PostgreSQL, automated SSL/TLS with Ingress, Prometheus/Grafana monitoring, and centralized EFK logging.
metrics: 100% automated SSL/TLS provisioning; 3 probe types (startup, liveness, readiness) with 10-min grace periods; automated daily backup scripts with log rotation.
---

### Self-Hosted GitLab CI/CD Platform on Kubernetes
*Kubernetes | Docker | NGINX Ingress | PostgreSQL | Prometheus | Grafana*

- Architected and deployed a multi-tier self-hosted GitLab CE platform transitioning from Docker Compose to production Kubernetes (Minikube).
- Configured isolated internal PostgreSQL database (ClusterIP) with persistent volume claims (PVCs) ensuring stateful persistence across node restarts.
- Implemented NGINX Ingress Controller with Cert-Manager ClusterIssuer for automated HTTPS encryption and secure external access.
- Integrated full observability stack: Prometheus metric scraping, custom Grafana dashboards, and centralized EFK (Elasticsearch, Fluent Bit, Kibana) log aggregation.
- Engineered automated operational Bash scripts (init.sh, backup.sh, deploy-k8s.sh) enforcing strict permission hardening (chmod 600) and Docker Secrets injection.

