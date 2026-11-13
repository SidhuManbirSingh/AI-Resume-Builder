---
id: gitlab_k8s_platform
title: Self-Hosted GitLab CI/CD Platform on Kubernetes
github_repo: SELF-HOSTED-GITLAB-CE-KUBERNETES
github_url: https://github.com/SidhuManbirSingh/SELF-HOSTED-GITLAB-CE-KUBERNETES
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
summary: "Intensive 75+ commit production-grade self-hosted GitLab CI/CD platform orchestrated with Kubernetes and Docker Compose, featuring external PostgreSQL, automated SSL/TLS with NGINX Ingress and Cert-Manager, Prometheus/Grafana monitoring, and centralized EFK logging."
metrics: "~75 Git commits of iterative systems engineering; 100% automated SSL/TLS provisioning; 3 probe types (startup, liveness, readiness) with 10-min grace periods; automated daily backup scripts with log rotation."
---

### Self-Hosted GitLab CI/CD Platform on Kubernetes | [GitHub](https://github.com/SidhuManbirSingh/SELF-HOSTED-GITLAB-CE-KUBERNETES)
*Kubernetes | Minikube | Docker Compose | NGINX Ingress | Cert-Manager | TLS/SSL | PostgreSQL | Prometheus | Grafana | EFK Stack | Bash (~75 Commits)*

- Architected and deployed a multi-tier self-hosted GitLab CE platform across ~75 iterative Git commits, migrating complex stateful services from Docker Compose to production Kubernetes (Minikube).
- Configured an isolated internal PostgreSQL database (`ClusterIP`) with Persistent Volume Claims (PVCs) and 3-tier health probes (startup, liveness, readiness with 10-minute grace periods) ensuring zero-data-loss persistence across node restarts.
- Implemented NGINX Ingress Controller with Cert-Manager `ClusterIssuer` for 100% automated SSL/TLS certificate provisioning, HTTPS encryption, and secure external routing.
- Integrated a full observability stack featuring Prometheus metric scraping, custom Grafana telemetry dashboards, and centralized EFK (Elasticsearch, Fluent Bit, Kibana) log aggregation.
- Engineered hardened operational Bash automation scripts (`init.sh`, `backup.sh`, `deploy-k8s.sh`) enforcing strict file permission security (`chmod 600`), automated daily backups with log rotation, and Docker Secrets injection.
