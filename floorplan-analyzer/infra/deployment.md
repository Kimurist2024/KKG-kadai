# AWS deployment

Terraform creates a small ECS Fargate deployment for the Next.js frontend and FastAPI backend. `.github/workflows/` belongs at the **repository root**, alongside `floorplan-analyzer/`. This setup has not created AWS resources or published images.

```text
Browser → HTTPS ALB → frontend:3000 → localhost:8000 backend → OpenAI
                       └── one Fargate task, two containers ──┘
```

The VPC has two public subnets in different availability zones and an internet gateway. Tasks receive a public IPv4 address for ECR, Secrets Manager, logs, and outbound HTTPS, avoiding a NAT gateway. Their security group permits inbound port 3000 **only from the ALB security group**. Port 8000 is not exposed externally. The ALB redirects HTTP to HTTPS; an existing validated ACM certificate is required. The steady-state service has one task (0.5 vCPU / 1 GiB), with up to two during rolling deployment, so this is not a multi-task high-availability setup. ALB, Fargate, public IPv4, logs and secrets incur charges.

## Prerequisites

- Terraform 1.10+, AWS CLI v2, Docker with buildx; Node.js 22 / Python 3.12 for local verification.
- AWS credentials with permission to provision the resources (the GitHub deploy role intentionally cannot provision infrastructure).
- A validated ACM certificate in the selected region and a domain you can point at the ALB.
- Two existing Secrets Manager secrets in the same region/account, containing **plain strings**, not JSON: the OpenAI API key and an application AI access token. Create their values outside Terraform. Terraform accepts ARNs only; it never reads secret values into state. With a customer-managed KMS key, set `secrets_kms_key_arn` and allow the execution role in the key policy.
- An existing ECS service-linked role, or provisioning credentials that allow AWS to create it. If necessary, an administrator runs `aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com` once per account.
- A GitHub repository with this workspace layout. Set the required `openai_model` to a vision model supported by the application and enabled for your OpenAI account. No model is selected automatically.

## First deployment: ECR → images → application

All commands below start in `floorplan-analyzer/`. Two independent Terraform states remove the dependency cycle: `bootstrap` creates only the image repositories; `app` references them after images exist. No `-target` is needed.

1. Initialize and create the registries with your own AWS credentials:

   ```bash
   terraform -chdir=infra/terraform/bootstrap init
   terraform -chdir=infra/terraform/bootstrap plan -out=bootstrap.tfplan
   terraform -chdir=infra/terraform/bootstrap apply bootstrap.tfplan
   ```

   Both roots default to `ap-northeast-1` and `floorplan-analyzer`. If you change `aws_region` or `project_name`, supply the same values to both roots using their own `terraform.tfvars` files.

2. Build and push the **committed revision** using a full commit SHA. Run from a clean checkout; never reuse the tag for changed source. ECR tags are immutable.

   ```bash
   export AWS_REGION=ap-northeast-1
   export FRONTEND_REPOSITORY=$(terraform -chdir=infra/terraform/bootstrap output -raw frontend_repository_url)
   export BACKEND_REPOSITORY=$(terraform -chdir=infra/terraform/bootstrap output -raw backend_repository_url)
   export IMAGE_TAG=$(git rev-parse HEAD)
   aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${FRONTEND_REPOSITORY%%/*}"
   docker buildx build --platform linux/amd64 --push -t "$FRONTEND_REPOSITORY:$IMAGE_TAG" frontend
   docker buildx build --platform linux/amd64 --push -t "$BACKEND_REPOSITORY:$IMAGE_TAG" backend
   ```

3. Copy `infra/terraform/app/terraform.tfvars.example` to `terraform.tfvars` in the same directory and replace **all** placeholder ARNs, repository names and image URIs. `frontend_image` / `backend_image` require full commit SHA tags or image digests. Set `github_repository` to the exact case-sensitive `owner/repository`.

   An AWS account has at most one OIDC provider for `token.actions.githubusercontent.com`. If one exists, set `github_oidc_provider_arn` to reuse it. Otherwise, Terraform creates it. The role trusts only the exact repository plus the configured GitHub environment, with audience `sts.amazonaws.com`.

   ```bash
   terraform -chdir=infra/terraform/app init
   terraform -chdir=infra/terraform/app plan -out=app.tfplan
   terraform -chdir=infra/terraform/app apply app.tfplan
   ```

4. Point a domain covered by the ACM certificate to the `alb_dns_name` output (Route 53 alias using `alb_zone_id`, or a subdomain CNAME). DNS and certificate issuance are intentionally external prerequisites. Verify `https://YOUR_DOMAIN/api/health` returns `{"status":"ok"}` and the UI opens. The ALB DNS hostname itself is not covered by your certificate; do not disable TLS verification.

## GitHub configuration and delivery

Create the GitHub environment `production` (or your chosen `github_environment`). Restrict its deployment branches to `main`; configure required reviewers if your repository plan supports them. The workflow also rejects deployment from other branches. If you use a different environment name, set the **repository-level** variable `DEPLOY_ENVIRONMENT` to that exact name.

Set these GitHub repository or environment **variables** (no long-lived AWS keys):

| Variable | Value |
|---|---|
| `AWS_REGION` | Region used by both Terraform roots |
| `AWS_DEPLOY_ROLE_ARN` | app output `github_deploy_role_arn` |
| `ECS_CLUSTER` | app output `ecs_cluster` |
| `ECS_SERVICE` | app output `ecs_service` |
| `ECR_FRONTEND` | bootstrap output `frontend_repository_url`, without tag |
| `ECR_BACKEND` | bootstrap output `backend_repository_url`, without tag |
| `APP_URL` | `https://YOUR_DOMAIN` without trailing slash |

`CI` runs pytest, frontend typecheck/tests/build, a Linux AMD64 Docker Compose build/start with health and sample-upload smoke checks, and Terraform formatting/validation on pull requests and pushes. It does not access AWS credentials. `Deploy to AWS` is manual (`workflow_dispatch`): select `main`. It runs the same CI first, obtains short-lived AWS credentials through OIDC, builds/pushes SHA-tagged images, copies the current task definition with updated image URIs, rolls the service out, waits for stability, verifies the active revision (detecting automatic rollback), then checks the HTTPS health endpoint through the frontend proxy. Rerunning the same commit reuses any existing immutable ECR images. No secret values are given to GitHub or included in Docker build arguments.

The deploy role can push only to the two project repositories, update only this ECS service, and pass only its execution/task roles to ECS. `RegisterTaskDefinition` is scoped to this project task family. `GetAuthorizationToken` and `DescribeTaskDefinition` require wildcard resource scope. The application task role has no AWS permissions; the execution role can pull these images, write its logs, and fetch the two specified secrets.

## Infrastructure changes, rotation and rollback

Terraform owns infrastructure and a baseline task definition. GitHub owns the service's active task revision after creation (`ignore_changes = [task_definition]` prevents Terraform from rolling back an image deployment). Therefore changing environment variables, secrets ARNs, CPU/memory, or container configuration in Terraform requires an **explicit rollout** after apply. First set the Terraform image variables to the currently desired SHA/digests, apply, then run with operator credentials:

```bash
export ECS_CLUSTER=$(terraform -chdir=infra/terraform/app output -raw ecs_cluster)
export ECS_SERVICE=$(terraform -chdir=infra/terraform/app output -raw ecs_service)
export TASK_REVISION=$(terraform -chdir=infra/terraform/app output -raw terraform_task_definition_arn)
aws ecs update-service --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" --task-definition "$TASK_REVISION"
aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE"
```

Updating the value of an existing secret requires new tasks (`aws ecs update-service ... --force-new-deployment`); running containers do not receive changed values automatically. Do not print or commit the token. Rolling back means selecting a previously healthy task definition ARN with `update-service`, waiting, and checking the public health endpoint. The ECS circuit breaker rolls back failed deployments automatically where a previous successful deployment exists. Keep known-good ECR images for rollback; no automatic image deletion policy is configured.

The rollout health check verifies API reachability, not model quality or an authenticated paid OpenAI request. Exercise the AI feature separately with an authorized token and representative input after deployment.

## State and validation

The example uses local state by default and never commits state, `.terraform/`, variable values, or plan files. Preserve both independent states securely. For a team, use an existing private encrypted, versioned S3 bucket with separate keys and state locking. Add a local `backend.tf` in each root before `init` (use a different key for `app`):

```hcl
terraform {
  backend "s3" {
    bucket       = "YOUR_PRIVATE_STATE_BUCKET"
    key          = "floorplan/bootstrap.tfstate"
    region       = "ap-northeast-1"
    encrypt      = true
    use_lockfile = true
  }
}
```

For an already-initialized root, migrate with `terraform init -migrate-state`. State and plan files still reveal infrastructure identifiers and must be protected even though secrets are not read. CI uses `init -backend=false` and only validates syntax/provider configuration; it does not run a live plan or test AWS permissions, quotas, certificate status or resource availability. Commit both `.terraform.lock.hcl` files. Terraform/provider downloads are required for validation.

To remove a deployment, review `terraform destroy` in `app` first. ECR repositories deliberately refuse deletion when nonempty (`force_delete = false`); decide image retention separately before removing `bootstrap`. Existing secrets, ACM certificates and external state buckets are not managed or deleted by these roots.

## Verification performed in this workspace

- Terraform 1.10.5: `fmt -check -recursive` passed; `init -backend=false` and `validate` passed for both roots using the signed AWS provider 6.64.0. Both lockfiles are included.
- actionlint 1.7.12: both workflows passed (`-shellcheck=`; ShellCheck was not installed). All 14 workflow shell blocks also passed `bash -n`.
- Docker is not installed here, so the Compose build/start and smoke checks are implemented in CI but have not run locally. No repository push, GitHub Actions run, AWS plan/apply, or live deployment has occurred.

## Official references

Confirmed 2026-09-14:

- [AWS Fargate networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html): task public IP, localhost communication and image-pull connectivity.
- [AWS ECS Secrets Manager environment variables](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html): execution-role permissions and restart requirements.
- [GitHub OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws): audience and exact repository/environment subject restrictions.
- [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3): state encryption and S3 lockfile configuration.

- [AWS ECS service authorization reference](https://docs.aws.amazon.com/pt_br/service-authorization/latest/reference/list_amazonelasticcontainerservice.html): task-family scope for registration and unscoped describe permission (the English example policy page has an older broader registration example).
