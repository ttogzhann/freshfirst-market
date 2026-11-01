# Issue #61 CI/CD design

This document records the static, reviewable workflow boundary for Issue #61.
It does not authorize AWS activation, deployment, or live-site verification.

## Workflow boundary

- [`ci.yml`](../.github/workflows/ci.yml) runs on pull requests and pushes to
  `main`. Its dependency chain is backend checks and frontend checks, then the
  production image build, real PostgreSQL Compose integration, and the existing
  isolated real-browser Playwright journey. A failure stops downstream jobs.
- The `deploy` job in [`ci.yml`](../.github/workflows/ci.yml) is only eligible
  on `workflow_dispatch`. It is restricted to the canonical repository and
  `refs/heads/main`, uses the `production` environment, depends on every CI job,
  and is the only job with `id-token: write`. The deployment role must trust exactly
  `repo:ttogzhann/freshfirst-market:environment:production`, audience
  `sts.amazonaws.com`, and `refs/heads/main`.
- The deploy job uses GitHub OIDC through the pinned AWS credentials action;
  there are no long-lived AWS keys. The CloudFormation service-role ARN is an
  explicit dispatch input and is passed to the existing
  [`freshfirst-ec2.yaml`](../deploy/aws/freshfirst-ec2.yaml) template. The
  production environment approval is the final workflow gate before AWS
  commands can run.
- Post-deploy checks are bounded health, API, and headless-browser requests to
  the supplied real origin. No PR or push path contains an AWS command.

Inputs, role ARNs, domains, image references, and origins are not stored in the
repository. Configure `AWS_DEPLOYMENT_ROLE_ARN` only as a protected production
environment secret. This candidate intentionally does not run the dispatch or
make any AWS call.

## Static validation without AWS

From the repository root, run these checks before review. They parse and scan
the workflow files only; none contacts AWS:

```sh
actionlint .github/workflows/*.yml
node frontend/node_modules/prettier/bin/prettier.cjs --config frontend/.prettierrc --check .github/workflows/*.yml docs/issue-61-ci-cd.md
git diff --check
gitleaks detect --no-banner --redact --source .
```

`actionlint` and `gitleaks` are external developer tools and may be unavailable
in a local environment. If unavailable, record that fact rather than replacing
the check with an AWS command. The workflow action pins were resolved from the
official release pages: checkout `11bd719...`, setup-python `a26af69...`,
setup-node `49933ea...`, and configure-aws-credentials `e125382...`; every
reference is the complete 40-character commit SHA in the workflow.
