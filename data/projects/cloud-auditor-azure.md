---
id: azure_cloud_security_auditor
title: Azure Cloud Security & Compliance Auditor
github_url: https://github.com/Balkar-S/Cloud-Security-Auditor
technologies:
  - Python
  - Azure SDK
  - Cloud Security
  - IAM
  - Network Security Groups
  - Encryption
  - Bash
domain: Cloud Security & Governance
status: completed
summary: Automated cloud security auditing tool detecting misconfigurations, overprivileged IAM roles, unencrypted storage, and permissive firewall rules in Azure environments.
metrics: 100% automated scanning across Storage Accounts, Network Security Groups, and IAM roles; generates structured JSON and CSV audit reports.
---

### Azure Cloud Security & Compliance Auditor | [GitHub](https://github.com/Balkar-S/Cloud-Security-Auditor)
*Python | Azure SDK | Cloud Security | IAM | NSG*

- Developed an automated security auditing script for Azure cloud environments detecting infrastructure misconfigurations and compliance violations.
- Audited Azure Storage Accounts for public blob exposure, deprecated TLS versions, and missing HTTPS enforcement.
- Analyzed Network Security Group (NSG) ingress and egress rules to flag overly permissive wildcard CIDR blocks and exposed management ports.
- Evaluated Azure Active Directory (Entra ID) and IAM role assignments to detect privilege creep and excess administrative permissions.
- Generated standardized timestamped audit reports in JSON and CSV formats for executive reviews and security compliance dashboards.
