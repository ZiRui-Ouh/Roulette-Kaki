#!/usr/bin/env bash
# One-time bootstrap: create the S3 bucket + DynamoDB lock table that Terraform's
# remote backend will use. Idempotent — safe to re-run.
#
# Prereqs: AWS CLI v2 authenticated (`aws sts get-caller-identity` works),
# jq installed.
#
# Env overrides:
#   AWS_REGION           default: us-east-1
#   TF_STATE_BUCKET      default: parl-tfstate-<accountid>
#   TF_LOCK_TABLE        default: parl-tf-locks

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
STATE_BUCKET="${TF_STATE_BUCKET:-parl-tfstate-${ACCOUNT_ID}}"
LOCK_TABLE="${TF_LOCK_TABLE:-parl-tf-locks}"

echo "==> Bootstrapping Terraform remote state"
echo "    region: ${REGION}"
echo "    bucket: ${STATE_BUCKET}"
echo "    lock:   ${LOCK_TABLE}"

if ! aws s3api head-bucket --bucket "${STATE_BUCKET}" 2>/dev/null; then
  echo "==> Creating S3 bucket ${STATE_BUCKET}"
  if [ "${REGION}" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "${STATE_BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket \
      --bucket "${STATE_BUCKET}" \
      --region "${REGION}" \
      --create-bucket-configuration LocationConstraint="${REGION}"
  fi
else
  echo "==> S3 bucket ${STATE_BUCKET} already exists"
fi

echo "==> Enabling versioning + encryption + public-access block on ${STATE_BUCKET}"
aws s3api put-bucket-versioning \
  --bucket "${STATE_BUCKET}" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "${STATE_BUCKET}" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block \
  --bucket "${STATE_BUCKET}" \
  --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

if ! aws dynamodb describe-table --table-name "${LOCK_TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  echo "==> Creating DynamoDB lock table ${LOCK_TABLE}"
  aws dynamodb create-table \
    --region "${REGION}" \
    --table-name "${LOCK_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --table-name "${LOCK_TABLE}" --region "${REGION}"
else
  echo "==> DynamoDB lock table ${LOCK_TABLE} already exists"
fi

cat <<EOF

Bootstrap complete.

  Terraform backend config (used by 10_infra.sh):
    bucket:         ${STATE_BUCKET}
    key:            parl/terraform.tfstate
    region:         ${REGION}
    dynamodb_table: ${LOCK_TABLE}

Next: run deploy/10_infra.sh
EOF
