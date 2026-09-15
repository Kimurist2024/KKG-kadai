variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}
variable "project_name" {
  type    = string
  default = "floorplan-analyzer"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.project_name))
    error_message = "Use 3-25 lowercase letters, digits or hyphens, starting with a letter."
  }
}
variable "frontend_image" {
  description = "Previously pushed ECR image URI, pinned to a full commit SHA tag or sha256 digest."
  type        = string
  validation {
    condition     = can(regex("(:[0-9a-f]{40}|@sha256:[0-9a-f]{64})$", var.frontend_image))
    error_message = "Pin the image to a full commit SHA tag or sha256 digest."
  }
}
variable "backend_image" {
  description = "Previously pushed ECR image URI, pinned to a full commit SHA tag or sha256 digest."
  type        = string
  validation {
    condition     = can(regex("(:[0-9a-f]{40}|@sha256:[0-9a-f]{64})$", var.backend_image))
    error_message = "Pin the image to a full commit SHA tag or sha256 digest."
  }
}
variable "certificate_arn" {
  description = "Existing, validated ACM certificate in aws_region, covering the public domain."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:acm:", var.certificate_arn))
    error_message = "An existing ACM certificate ARN is required."
  }
}
variable "openai_api_key_secret_arn" {
  description = "Existing Secrets Manager secret ARN; its entire plaintext value is the API key."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:secretsmanager:[^:]+:[0-9]{12}:secret:", var.openai_api_key_secret_arn))
    error_message = "Provide a Secrets Manager secret ARN, never a secret value."
  }
}
variable "ai_access_token_secret_arn" {
  description = "Existing Secrets Manager secret ARN; entire plaintext value is the AI access token."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:secretsmanager:[^:]+:[0-9]{12}:secret:", var.ai_access_token_secret_arn))
    error_message = "Provide a Secrets Manager secret ARN, never a secret value."
  }
}
variable "secrets_kms_key_arn" {
  description = "Optional customer-managed KMS key used by both secrets; null for the AWS-managed key."
  type        = string
  default     = null
}
variable "openai_model" {
  description = "Vision model ID supported by the application and enabled for your OpenAI account; select explicitly."
  type        = string
  validation {
    condition     = length(trimspace(var.openai_model)) > 0 && !startswith(var.openai_model, "REPLACE_")
    error_message = "Choose an enabled OpenAI vision model ID explicitly."
  }
}
variable "github_repository" {
  description = "Exact case-sensitive GitHub owner/repository allowed to deploy."
  type        = string
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use owner/repository without wildcards."
  }
}
variable "github_environment" {
  type    = string
  default = "production"
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]+$", var.github_environment))
    error_message = "Use letters, digits, hyphens or underscores only."
  }
}
variable "github_oidc_provider_arn" {
  description = "Existing token.actions.githubusercontent.com OIDC provider ARN, or null to create one."
  type        = string
  default     = null
}
