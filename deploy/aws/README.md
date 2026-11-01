# FreshFirst AWS EC2 architecture (Issue #60)

This is a reviewable, approval-gated design for a small single-EC2 deployment of
the production-built FreshFirst container. It is intentionally not a deployment
runbook that has been executed. No AWS account, stack, DNS record, certificate,
role, budget, or paid resource was created for Issue #60.

## Architecture and traffic path

```text
Browser -- HTTPS :443 / HTTP :80 --> Caddy (public EC2 host network)
                                      | reverse_proxy, one origin
                                      v
                              app (private Compose network :8000)
                                      |
                                      v
                          PostgreSQL (private Compose network :5432)
                                      |
                                      v
                         encrypted gp3 EBS-backed Docker volume
```

The template creates one public subnet and one security group. Only TCP 80 and
443 are allowed from the internet. There is no SSH rule and PostgreSQL has no
published port. The application is reached through Caddy, so SSR, API calls,
cookies, CSRF, and the browser's origin remain aligned as they were in the
verified Compose/E2E candidate. Caddy obtains and renews the certificate for
`DomainName` using the normal ACME flow after DNS points at the instance.

The app image is an immutable operator-supplied URI, preferably a digest. The
EC2 bootstrap installs Docker, retrieves two generated secret values from AWS
Secrets Manager, writes a mode-0600 Compose environment
file, and starts `db`, then the health-gated `app`, then Caddy. The template is
not a substitute for an approved release process; CI/CD and image promotion are
Issue #61.

## Storage, backup, and recovery

- PostgreSQL data is a named Compose volume stored on the encrypted gp3 root EBS
  volume. The root volume is deleted with the instance only after an operator
  has taken/verified a snapshot; this is a deliberate recovery gate.
- Before production traffic, schedule encrypted EBS snapshots (daily, retain
  seven; weekly, retain four) with an approved backup account/key policy. A
  snapshot is not a substitute for a PostgreSQL logical dump: also run a
  periodic `pg_dump --format=custom` to an encrypted, access-controlled S3
  bucket with a retention/lifecycle policy. S3 and snapshot costs are variable.
- Recovery is: stop Caddy, restore a new encrypted EBS volume or a clean
  replacement instance from the last verified snapshot, restore the logical dump
  if needed, start the Compose health chain, validate `/healthz`, authenticate
  with a disposable account, and only then repoint DNS. Preserve the old volume
  read-only until the recovery is accepted.
- A single instance and local PostgreSQL are a proof-of-concept boundary, not
  high availability. Instance, EBS, AZ, Caddy, and operator errors remain
  outage boundaries. RDS, multi-AZ, WAF, and a load balancer are intentionally
  deferred.

## IAM and approval boundaries

[`freshfirst-ec2.yaml`](./freshfirst-ec2.yaml) contains:

- an EC2 instance role limited to the two stack-scoped Secrets Manager ARNs, pull-only
  ECR access to `freshfirst`, and the minimum SSM agent channels;
- a conditional future GitHub OIDC deployment role, created only if an existing
  OIDC provider ARN is supplied, with the exact repository/environment/ref
  conditions, scoped ECR push, SSM command access to the one instance, and
  `iam:PassRole` only for the runtime role and only to EC2;
- no IAM users, access keys, `AdministratorAccess`, SSH key requirement, or
  wildcard resource permission where AWS supports resource scoping. The ECR
  authorization-token and SSM agent channel APIs require `Resource: '*'` by AWS
  API design and are explicitly isolated in separate statements.

The future OIDC trust is intentionally environment-bound:
`repo:ttogzhann/freshfirst-market:environment:production`, with audience
`sts.amazonaws.com` and `refs/heads/main`. Before enabling it, the owner must
approve the GitHub environment protection rules, repository/ref, role ARN,
deployment commands, and `iam:PassRole` target. #61 owns the actual workflow.

## Cost estimate and guardrails

Estimate for `us-east-1`, 730 hours/month, on-demand `t3.small`, one 30 GiB gp3
volume, one in-use public IPv4 address, no NAT Gateway, no load balancer, no
paid certificate, and light traffic. Prices are USD and exclude tax, data
transfer, snapshots, S3, domain registration, and Free Tier/credits.

| Component | Low / expected assumption | Approx. monthly |
| --- | --- | ---: |
| EC2 `t3.small` | 730 × $0.0209/hour | $15.26 |
| gp3 EBS | 30 GiB × $0.08/GB-month | $2.40 |
| Public IPv4 | 730 × $0.005/hour | $3.65 |
| Secrets Manager | 2 secrets × $0.40/month | $0.80 |
| VPC / route / security group | no separate hourly charge in this shape | $0 |
| **Expected baseline** | always-on, light traffic | **$22.11** |

Planning ranges are approximately **$0–$8/month low** (free-tier/credits and
the instance stopped for most of the month), **$21–$35/month expected** (the
baseline plus modest snapshots, S3, and egress), and **$40–$80+/month high** if
the instance is always on with heavier egress, extra snapshots/storage, domain,
or recovery activity. A 30 GiB gp3 volume is within the commonly advertised
30 GiB EBS Free Tier only when the account qualifies; verify the account's
current eligibility before relying on it. Certificate issuance by Caddy/ACME is
normally free; domain registration is not.

Sources checked 2026-11-01:

- [EC2 T3 pricing](https://aws.amazon.com/ec2/instance-types/t3/) lists
  `t3.small` at $0.0209/hour in the displayed on-demand table.
- [EBS pricing](https://aws.amazon.com/ebs/pricing/) documents gp3 billing and
  the 30 GiB Free Tier qualification; the gp3 example rate is $0.08/GB-month.
- [VPC pricing](https://aws.amazon.com/vpc/pricing/) lists public IPv4 at
  $0.005/hour and describes the charge for in-use addresses.
- [AWS Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/)
  states that the first two monitoring budgets are free; action-enabled budget
  behavior and notification delivery still need owner review.

Create a monthly cost budget for the account at **$35**, notify the owner at
80% actual and forecasted spend, and review at $35. This is an alert, not a hard
spend cap; egress, snapshots, S3, domain, and tax can still exceed it. Do not
create the budget until the owner approves the account, region, notification
address, threshold, and whether budget actions are permitted.

## Explicit authorization gate

Before any future operator runs CloudFormation, the owner must separately
approve, in writing:

1. AWS account and region (`us-east-1` is only the estimate above), instance
   type/volume size, generated Secrets Manager values, budget recipient and $35 alert threshold;
2. domain ownership, DNS provider/change, public IP strategy, and ACME/TLS
   certificate issuance;
3. the exact immutable app image digest, generated PostgreSQL/auth secret policy,
   Secrets Manager/KMS/S3/snapshot retention, and restore drill;
4. VPC/EC2/EBS/Secrets Manager/ECR/IAM/OIDC resources and their teardown;
5. GitHub production environment protection and the future OIDC role/trust;
6. the public verification window and acceptance of the single-instance outage
   model.

No approval is implied by this template, a QA PASS, or an issue closure. Do not
run `aws cloudformation deploy`, `aws cloudformation create-stack`, IAM, DNS,
ACM, EC2, VPC, EBS, Secrets Manager, SSM, ECR, budget, or CloudFormation delete commands for
Issue #60.

## Safe operator lifecycle (future, after approval)

1. Validate the template and IAM/security diff locally; obtain all approvals.
2. Create the stack in the approved region with fresh secret values supplied
   interactively or by an approved secret manager, never a committed file.
3. Create DNS only after the instance address is known; wait for Caddy's ACME
   certificate and `/healthz`.
4. Run the existing real-browser Compose-style acceptance against the public
   origin using a disposable account, then inspect account isolation and logs.
5. For updates, pull the new immutable image, recreate only `app`, wait for
   health, and retain the prior image tag for rollback. Never delete the
   PostgreSQL volume during an application update.
6. For teardown, take and verify backups, remove DNS only after the public site
   is intentionally offline, then delete the stack and separately confirm no
   snapshots, EIPs, S3 objects, ECR images, Secrets Manager secrets, or IAM roles remain.

Issue #61 owns the later CI/CD workflow. Issue #62 owns approved live-site
verification and operational cost evidence. No part of this document claims
that either has begun.
