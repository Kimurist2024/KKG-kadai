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
