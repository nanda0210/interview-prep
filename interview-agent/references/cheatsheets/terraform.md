# Cheatsheet — Terraform / Terragrunt

## State backend (S3 + DynamoDB)
```hcl
terraform {
  backend "s3" {
    bucket         = "tfstate-cxp"
    key            = "accounts/cxp-apps-platform-dev/us-west-2/eks/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "tfstate-locks"
    encrypt        = true
  }
}
```
Lock = DynamoDB item `LockID = <bucket>/<key>-md5`.

## Common module patterns
- `vpc` (terraform-aws-modules/vpc/aws) → outputs subnet IDs.
- `eks` (terraform-aws-modules/eks/aws) → cluster + addons + access entries.
- `iam-role-for-service-accounts-eks` → IRSA roles per workload.
- `karpenter` → controller IRSA + EC2NodeClass IAM.

## Terragrunt — DRY pattern
```
live/
  cxp-apps-platform-dev/
    us-west-2/
      vpc/terragrunt.hcl
      eks/terragrunt.hcl       # depends_on vpc
      addons/terragrunt.hcl    # depends_on eks
```
- `terragrunt.hcl` includes `root.hcl` (backend, provider).
- `dependency "vpc" { config_path = "../vpc" }` → wire outputs.

## State surgery
```bash
terraform state list
terraform state mv aws_security_group.old aws_security_group.new
terraform import aws_eks_cluster.x my-cluster
terraform state rm aws_iam_role.gone
```

## Drift detection in CI
- Nightly `terragrunt run-all plan` → fail if non-zero diff for designated stacks.
- For stacks with intentional out-of-band changes: `lifecycle { ignore_changes = [tags["LastModified"]] }`.

## Dangerous moves
- `terragrunt run-all apply` in prod → parallel, no atomicity, partial-failure risk.
- `terraform destroy` without `-target` on a shared module.
- Editing `aws-auth` ConfigMap from TF + ArgoCD simultaneously → fight loop.

## PR checks worth enforcing
- `terraform fmt -check`
- `terraform validate`
- `tflint`
- `tfsec` / `checkov`
- `terraform plan` posted as PR comment
- `JiraID` tag present (per cxp-platform standards)
