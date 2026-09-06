# Remote state backend.
#
# Bucket + lock table are provisioned by `deploy/00_bootstrap.sh` before
# `terraform init` is first run. Partial config here — actual bucket / table
# names are passed via `-backend-config` in `deploy/10_infra.sh` so the
# account ID stays out of the repo.
#
# Migration from the previous local-state setup:
#   1. Commit any pending changes.
#   2. Run `deploy/00_bootstrap.sh` (idempotent).
#   3. Run `terraform init -reconfigure -migrate-state -backend-config=...`.
#   4. Delete terraform.tfstate + terraform.tfstate.backup from git, add to
#      .gitignore.
terraform {
  backend "s3" {}
}
