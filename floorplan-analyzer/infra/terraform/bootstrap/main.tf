terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
provider "aws" {
  region = var.aws_region
}
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
resource "aws_ecr_repository" "app" {
  for_each             = toset(["frontend", "backend"])
  name                 = "${var.project_name}-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration {
    scan_on_push = true
  }
}
output "frontend_repository_url" {
  value = aws_ecr_repository.app["frontend"].repository_url
}
output "backend_repository_url" {
  value = aws_ecr_repository.app["backend"].repository_url
}
