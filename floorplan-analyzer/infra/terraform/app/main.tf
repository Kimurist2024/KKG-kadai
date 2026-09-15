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
  default_tags {
    tags = { Project = var.project_name, ManagedBy = "Terraform" }
  }
}
data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_caller_identity" "current" {}
data "aws_ecr_repository" "frontend" {
  name = "${var.project_name}-frontend"
}
data "aws_ecr_repository" "backend" {
  name = "${var.project_name}-backend"
}
locals {
  repositories = [data.aws_ecr_repository.frontend.arn, data.aws_ecr_repository.backend.arn]
  secret_arns  = [var.openai_api_key_secret_arn, var.ai_access_token_secret_arn]
  account_id   = data.aws_caller_identity.current.account_id
}
resource "aws_vpc" "app" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}
resource "aws_internet_gateway" "app" {
  vpc_id = aws_vpc.app.id
}
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.app.id
  cidr_block              = cidrsubnet(aws_vpc.app.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.app.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.app.id
  }
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "alb" {
  name   = "${var.project_name}-alb"
  vpc_id = aws_vpc.app.id
}
resource "aws_security_group" "task" {
  name   = "${var.project_name}-task"
  vpc_id = aws_vpc.app.id
}
resource "aws_vpc_security_group_ingress_rule" "web" {
  for_each          = toset(["80", "443"])
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = tonumber(each.key)
  to_port           = tonumber(each.key)
}
resource "aws_vpc_security_group_egress_rule" "alb" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.task.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
}
resource "aws_vpc_security_group_ingress_rule" "task" {
  security_group_id            = aws_security_group.task.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
}
resource "aws_vpc_security_group_egress_rule" "task" {
  security_group_id = aws_security_group.task.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
resource "aws_lb" "app" {
  name               = var.project_name
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 120
}
resource "aws_lb_target_group" "app" {
  name        = var.project_name
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.app.id
  health_check {
    path                = "/api/health"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
}
resource "aws_ecs_cluster" "app" {
  name = var.project_name
}
resource "aws_iam_role" "execution" {
  name = "${var.project_name}-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}
resource "aws_iam_role_policy" "execution" {
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"], Resource = local.repositories },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = local.secret_arns }
      ], var.secrets_kms_key_arn == null ? [] : [{
        Effect    = "Allow", Action = ["kms:Decrypt"], Resource = var.secrets_kms_key_arn,
        Condition = { StringEquals = { "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com" } }
    }])
  })
}
resource "aws_iam_role" "task" {
  name = "${var.project_name}-task"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  # The application itself needs no AWS API permissions.
}
resource "aws_ecs_task_definition" "app" {
  family                   = var.project_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([
    {
      name         = "backend", image = var.backend_image, essential = true,
      portMappings = [{ containerPort = 8000, protocol = "tcp" }],
      environment  = [{ name = "OPENAI_MODEL", value = var.openai_model }],
      secrets = [
        { name = "OPENAI_API_KEY", valueFrom = var.openai_api_key_secret_arn },
        { name = "AI_ACCESS_TOKEN", valueFrom = var.ai_access_token_secret_arn }
      ],
      healthCheck = {
        command  = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"],
        interval = 30, timeout = 5, retries = 3, startPeriod = 30
      },
      logConfiguration = {
        logDriver = "awslogs",
        options   = { awslogs-group = aws_cloudwatch_log_group.app.name, awslogs-region = var.aws_region, awslogs-stream-prefix = "backend" }
      }
    },
    {
      name         = "frontend", image = var.frontend_image, essential = true,
      portMappings = [{ containerPort = 3000, protocol = "tcp" }],
      environment  = [{ name = "API_PROXY_TARGET", value = "http://127.0.0.1:8000" }, { name = "PORT", value = "3000" }, { name = "HOSTNAME", value = "0.0.0.0" }],
      dependsOn    = [{ containerName = "backend", condition = "HEALTHY" }],
      logConfiguration = {
        logDriver = "awslogs",
        options   = { awslogs-group = aws_cloudwatch_log_group.app.name, awslogs-region = var.aws_region, awslogs-stream-prefix = "frontend" }
      }
    }
  ])
  lifecycle {
    precondition {
      condition     = startswith(var.frontend_image, "${data.aws_ecr_repository.frontend.repository_url}:") || startswith(var.frontend_image, "${data.aws_ecr_repository.frontend.repository_url}@")
      error_message = "frontend_image must belong to the bootstrap frontend ECR repository."
    }
    precondition {
      condition     = startswith(var.backend_image, "${data.aws_ecr_repository.backend.repository_url}:") || startswith(var.backend_image, "${data.aws_ecr_repository.backend.repository_url}@")
      error_message = "backend_image must belong to the bootstrap backend ECR repository."
    }
  }
}
resource "aws_ecs_service" "app" {
  name                               = var.project_name
  cluster                            = aws_ecs_cluster.app.id
  task_definition                    = aws_ecs_task_definition.app.arn
  desired_count                      = 1
  launch_type                        = "FARGATE"
  platform_version                   = "1.4.0"
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  wait_for_steady_state              = true
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "frontend"
    container_port   = 3000
  }
  lifecycle {
    # CI/CD owns the active task revision after the initial Terraform deployment.
    ignore_changes = [task_definition]
  }
  depends_on = [aws_lb_listener.https, aws_iam_role_policy.execution, aws_route_table_association.public]
}
