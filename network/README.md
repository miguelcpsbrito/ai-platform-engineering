# network/ — private paths and egress control (Section 3.3)

**Proves:** a direct provider-API call from a workload subnet resolves to NXDOMAIN, and
Bedrock resolves to a private address.

- `hub/` — VPC with workload, endpoint, public (NAT) and optional firewall subnets; route tables per AZ.
- `main.tf` — the bedrock-runtime endpoint restricted to platform roles (Figure 3.4), the other interface endpoints, S3 gateway endpoint, DNS Firewall (domain list, rule, rule group association) and resolver query logging.
- `firewall.tf` — the optional Network Firewall track: SNI/Host deny list and symmetric routing through the firewall endpoints (≈ $9.50/day per AZ).

Not included: Transit Gateway attachments for spoke VPCs.
